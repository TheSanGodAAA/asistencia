from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime
from db.database import get_conn

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

def _minutos_from_override(entrada_iso: str | None, salida_iso: str | None) -> int | None:
    if not entrada_iso or not salida_iso:
        return None
    ent = datetime.fromisoformat(entrada_iso)
    sal = datetime.fromisoformat(salida_iso)
    if sal <= ent:
        return None
    return int((sal - ent).total_seconds() // 60)


def crear_borrador_liquidacion(anio: int, mes: int) -> int:
    _, last_day = monthrange(anio, mes)
    d1 = date(anio, mes, 1)
    d2 = date(anio, mes, last_day)
    now = datetime.now().isoformat()

    with get_conn() as conn:
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
        tot_monto = {}

        for emp_id, fecha_s, minutos_calc, ent_man, sal_man in rows:
            dd = date.fromisoformat(fecha_s)

            minutos_override = _minutos_from_override(ent_man, sal_man)
            minutos = minutos_override if minutos_override is not None else int(minutos_calc)

            tarifa = _tarifa_cent(conn, emp_id, dd)
            monto = _monto_cent(minutos, tarifa)

            tot_min[emp_id] = tot_min.get(emp_id, 0) + minutos
            tot_monto[emp_id] = tot_monto.get(emp_id, 0) + monto

        for emp_id in sorted(tot_min.keys()):
            tarifa_fin_mes = _tarifa_cent(conn, emp_id, d2)
            conn.execute(
                """
                INSERT INTO liquidacion_detalle
                (liquidacion_id, empleado_id, minutos_pagados, pago_hora_cent, monto_cent)
                VALUES (?, ?, ?, ?, ?)
                """,
                (liquidacion_id, emp_id, tot_min[emp_id], tarifa_fin_mes, tot_monto[emp_id]),
            )

        return liquidacion_id

def cerrar_liquidacion(anio: int, mes: int) -> None:
    now = datetime.now().isoformat()
    with get_conn() as conn:
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
