from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from db.database import get_conn


def _ensure_vales_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vales (
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          empleado_id   INTEGER NOT NULL,
          fecha         TEXT    NOT NULL,
          monto_cent    INTEGER NOT NULL CHECK(monto_cent >= 0),
          nota          TEXT,
          creado_en     TEXT    NOT NULL,
          FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_vales_emp_fecha
          ON vales(empleado_id, fecha)
        """
    )
    vales_cols = {r[1] for r in conn.execute("PRAGMA table_info(vales)").fetchall()}
    if "es_arrastre" not in vales_cols:
        conn.execute("ALTER TABLE vales ADD COLUMN es_arrastre INTEGER NOT NULL DEFAULT 0")
    if "origen_anio" not in vales_cols:
        conn.execute("ALTER TABLE vales ADD COLUMN origen_anio INTEGER")
    if "origen_mes" not in vales_cols:
        conn.execute("ALTER TABLE vales ADD COLUMN origen_mes INTEGER")

    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_vales_arrastre_origen
          ON vales(es_arrastre, origen_anio, origen_mes)
        """
    )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(liquidacion_detalle)").fetchall()}
    required = {
        "id",
        "liquidacion_id",
        "empleado_id",
        "minutos_pagados",
        "pago_hora_cent",
        "monto_cent",
        "vales_cent",
        "monto_final_cent",
    }
    missing = sorted(required - cols)
    if missing:
        raise RuntimeError(
            "Schema de liquidacion_detalle desactualizado. "
            "Ejecuta: python db/migrate_20260305_liquidacion_detalle.py "
            f"(faltan columnas: {', '.join(missing)})"
        )


def _tarifa_cent(conn, empleado_id: int, d: date) -> int:
    row = conn.execute(
        """
        SELECT pago_hora_cent
        FROM tarifas_empleado
        WHERE empleado_id = ? AND desde <= ?
        ORDER BY desde DESC
        LIMIT 1
        """,
        (empleado_id, d.isoformat()),
    ).fetchone()
    if not row:
        raise RuntimeError(f"Empleado {empleado_id} sin tarifa vigente para {d.isoformat()}")
    return int(row[0])

def _monto_cent(minutos: int, pago_hora_cent: int) -> int:
    # monto_cent = minutos * (cent/hora) / 60, redondeo a centésimo
    return (minutos * pago_hora_cent + 30) // 60

def _minutos_from_override(entrada_iso: str | None, salida_iso: str | None, fecha_s: str) -> int | None:
    """Calcula minutos desde valores de override que pueden ser hora sola (HH:MM[:SS])
    o ISO completo. `fecha_s` es la fecha de la jornada (YYYY-MM-DD) para combinar
    cuando las entradas son hora sola.
    """
    if not entrada_iso or not salida_iso:
        return None

    def _to_dt(s: str):
        if "T" in s or ("-" in s and "T" in s):
            return datetime.fromisoformat(s)
        fmt = "%H:%M:%S" if s.count(":") == 2 else "%H:%M"
        t = datetime.strptime(s, fmt).time()
        return datetime.combine(date.fromisoformat(fecha_s), t)

    try:
        ent = _to_dt(entrada_iso)
        sal = _to_dt(salida_iso)
    except Exception:
        return None

    if sal <= ent:
        return None
    return int((sal - ent).total_seconds() // 60)


def crear_borrador_liquidacion(anio: int, mes: int) -> int:
    _, last_day = monthrange(anio, mes)
    d1 = date(anio, mes, 1)
    d2 = date(anio, mes, last_day)
    now = datetime.now().isoformat()

    with get_conn() as conn:
        _ensure_vales_schema(conn)

        # si ya existe, la reutilizamos (si no está cerrada) y borramos detalle
        row = conn.execute(
            "SELECT id, estado FROM liquidaciones WHERE anio=? AND mes=?",
            (anio, mes),
        ).fetchone()

        if row and row[1] == "CERRADO":
            raise RuntimeError("La liquidación está CERRADA. No se puede recalcular.")

        if not row:
            cur = conn.execute(
                """
                INSERT INTO liquidaciones (anio, mes, estado, creado_en)
                VALUES (?, ?, 'BORRADOR', ?)
                """,
                (anio, mes, now),
            )
            liquidacion_id = cur.lastrowid
        else:
            liquidacion_id = row[0]
            conn.execute("DELETE FROM liquidacion_detalle WHERE liquidacion_id=?", (liquidacion_id,))

        rows = conn.execute(
            """
            SELECT
                j.empleado_id,
                j.fecha,
                j.minutos_calc,
                (
                SELECT o.entrada_manual
                FROM jornadas_override o
                WHERE o.jornada_id = j.id
                ORDER BY o.creado_en DESC
                LIMIT 1
                ) AS entrada_manual,
                (
                SELECT o.salida_manual
                FROM jornadas_override o
                WHERE o.jornada_id = j.id
                ORDER BY o.creado_en DESC
                LIMIT 1
                ) AS salida_manual
            FROM jornadas j
            WHERE j.fecha BETWEEN ? AND ?
            AND j.minutos_calc IS NOT NULL
            AND j.estado IN ('OK','FERIADO_PAGO')
            """,
            (d1.isoformat(), d2.isoformat()),
        ).fetchall()

        tot_min = {}
        tot_bruto = {}

        for emp_id, fecha_s, minutos_calc, ent_man, sal_man in rows:
            dd = date.fromisoformat(fecha_s)

            minutos_override = _minutos_from_override(ent_man, sal_man, fecha_s)
            minutos = minutos_override if minutos_override is not None else int(minutos_calc)

            tarifa = _tarifa_cent(conn, emp_id, dd)
            monto = _monto_cent(minutos, tarifa)

            tot_min[emp_id] = tot_min.get(emp_id, 0) + minutos
            tot_bruto[emp_id] = tot_bruto.get(emp_id, 0) + monto

        vales_rows = conn.execute(
            """
            SELECT empleado_id, COALESCE(SUM(monto_cent), 0)
            FROM vales
            WHERE fecha BETWEEN ? AND ?
            GROUP BY empleado_id
            """,
            (d1.isoformat(), d2.isoformat()),
        ).fetchall()
        vales_mes = {int(emp_id): int(monto) for emp_id, monto in vales_rows}

        empleados_liquidar = set(tot_min.keys()) | set(vales_mes.keys())

        # Recalcular es idempotente: borrar arrastres auto-generados previamente por este mismo mes.
        conn.execute(
            "DELETE FROM vales WHERE es_arrastre = 1 AND origen_anio = ? AND origen_mes = ?",
            (anio, mes),
        )

        if mes == 12:
            next_year, next_month = anio + 1, 1
        else:
            next_year, next_month = anio, mes + 1
        next_date = date(next_year, next_month, 1).isoformat()

        for emp_id in sorted(empleados_liquidar):
            minutos = int(tot_min.get(emp_id, 0))
            bruto = int(tot_bruto.get(emp_id, 0))
            vales = int(vales_mes.get(emp_id, 0))

            neto_raw = bruto - vales
            if neto_raw >= 0:
                neto = neto_raw
                arrastre_nuevo = 0
            else:
                # El monto final puede ser negativo para mostrar deuda del empleado.
                # Ademas, el exceso se transforma en un vale ficticio del mes siguiente.
                neto = neto_raw
                arrastre_nuevo = -neto_raw

            if minutos > 0:
                tarifa_fin_mes = _tarifa_cent(conn, emp_id, d2)
            else:
                row_tar = conn.execute(
                    """
                    SELECT pago_hora_cent FROM tarifas_empleado
                    WHERE empleado_id = ? AND desde <= ?
                    ORDER BY desde DESC LIMIT 1
                    """,
                    (emp_id, d2.isoformat()),
                ).fetchone()
                tarifa_fin_mes = int(row_tar[0]) if row_tar else 0

            if minutos > 0 or vales > 0:
                conn.execute(
                    """
                    INSERT INTO liquidacion_detalle
                    (liquidacion_id, empleado_id, minutos_pagados, pago_hora_cent, monto_cent, vales_cent, monto_final_cent)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        liquidacion_id,
                        emp_id,
                        minutos,
                        tarifa_fin_mes,
                        bruto,
                        vales,
                        neto,
                    ),
                )

            if arrastre_nuevo > 0:
                conn.execute(
                    """
                    INSERT INTO vales
                    (empleado_id, fecha, monto_cent, nota, creado_en, es_arrastre, origen_anio, origen_mes)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        emp_id,
                        next_date,
                        arrastre_nuevo,
                        f"Arrastre de vales {anio}-{mes:02d}",
                        now,
                        anio,
                        mes,
                    ),
                )

        return liquidacion_id

def cerrar_liquidacion(anio: int, mes: int) -> None:
    now = datetime.now().isoformat()
    with get_conn() as conn:
        _ensure_vales_schema(conn)
        row = conn.execute(
            "SELECT id, estado FROM liquidaciones WHERE anio=? AND mes=?",
            (anio, mes),
        ).fetchone()
        if not row:
            raise RuntimeError("No existe liquidación para cerrar.")
        if row[1] == "CERRADO":
            return
        conn.execute(
            """
            UPDATE liquidaciones
            SET estado='CERRADO', cerrado_en=?
            WHERE anio=? AND mes=?
            """,
            (now, anio, mes),
        )
