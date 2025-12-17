from collections import defaultdict
from datetime import datetime, date, time, timedelta

from db.database import get_conn

# Descanso estándar (se paga si el "gap" cubre todo el descanso)
DESC_INI = time(12, 15)
DESC_FIN = time(13, 0)
DESC_MIN = 45


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _get_horario(conn, d: date):
    row = conn.execute(
        """
        SELECT hora_inicio, hora_fin, tolerancia_min
        FROM horarios_vigencia
        WHERE desde <= ?
        ORDER BY desde DESC
        LIMIT 1
        """,
        (d.isoformat(),),
    ).fetchone()
    if not row:
        raise RuntimeError("No hay horario vigente configurado")

    hi, hf, tol = row
    hi_t = datetime.strptime(hi, "%H:%M").time()
    hf_t = datetime.strptime(hf, "%H:%M").time()
    return hi_t, hf_t, int(tol)


def _es_feriado(conn, d: date) -> bool:
    row = conn.execute("SELECT 1 FROM feriados WHERE fecha = ?", (d.isoformat(),)).fetchone()
    return bool(row)


def _control_descanso(conn, empleado_id: int) -> bool:
    row = conn.execute("SELECT control_descanso FROM empleados WHERE id = ?", (empleado_id,)).fetchone()
    return bool(row and row[0] == 1)


def _clamp_entrada(ts: datetime, hi: time, tol_min: int = 10) -> datetime:
    inicio = ts.replace(hour=hi.hour, minute=hi.minute, second=0, microsecond=0)
    if ts <= inicio:
        return inicio
    if ts <= inicio + timedelta(minutes=tol_min):
        return inicio
    return ts


def _clamp_salida(ts: datetime, hf: time, tol_salida_min: int = 10) -> datetime:
    fin = ts.replace(hour=hf.hour, minute=hf.minute, second=0, microsecond=0)
    if ts >= fin:
        return fin
    if ts >= fin - timedelta(minutes=tol_salida_min):
        return fin
    return ts


def _motivo_incompleto_o_multiple(n_ent: int, n_sal: int) -> str:
    if n_ent == 0 and n_sal == 1:
        return "Falta entrada"
    if n_ent == 1 and n_sal == 0:
        return "Falta salida"
    if n_ent == 0 and n_sal == 0:
        return "Sin marcaciones"
    if n_ent > 1 and n_sal == 1:
        return "Doble entrada"
    if n_ent == 1 and n_sal > 1:
        return "Doble salida"
    return "Marcas múltiples/incoherentes"


def _calc_horario_partido(eventos_orden, d: date, hi: time, hf: time, tol: int):
    """
    eventos_orden: lista [(tipo, ts)] ordenada por ts
    Caso soportado: ENT, SAL, ENT, SAL (2 tramos).
    Devuelve: (ent_calc, sal_calc, minutos, detalle) o None si no aplica.
    """
    tipos = [t for t, _ in eventos_orden]
    if not (len(eventos_orden) == 4 and tipos == ["ENT", "SAL", "ENT", "SAL"]):
        return None

    ent1 = eventos_orden[0][1]
    sal1 = eventos_orden[1][1]
    ent2 = eventos_orden[2][1]
    sal2 = eventos_orden[3][1]

    ent1 = _clamp_entrada(ent1, hi, tol)
    sal2 = _clamp_salida(sal2, hf)

    # Validación mínima de orden
    if not (ent1 < sal1 <= ent2 < sal2):
        return (ent1, sal2, None, "Horario partido inválido (orden de marcas)")

    tramo1 = int((sal1 - ent1).total_seconds() // 60)
    tramo2 = int((sal2 - ent2).total_seconds() // 60)

    # pagar descanso si el "gap" cubre completamente [12:15, 13:00]
    desc_ini_dt = datetime.combine(d, DESC_INI)
    desc_fin_dt = datetime.combine(d, DESC_FIN)
    paga_desc = (sal1 <= desc_ini_dt) and (ent2 >= desc_fin_dt)

    minutos = tramo1 + tramo2 + (DESC_MIN if paga_desc else 0)
    detalle = "Horario partido" + (" (incluye descanso pago)" if paga_desc else "")
    return (ent1, sal2, minutos, detalle)


def calcular_jornadas(desde: date, hasta: date):
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM jornadas WHERE fecha BETWEEN ? AND ?",
            (desde.isoformat(), hasta.isoformat()),
        )

        rows = conn.execute(
            """
            SELECT m.empleado_id, m.ts, m.tipo
            FROM marcaciones m
            WHERE date(m.ts) BETWEEN ? AND ?
            ORDER BY m.empleado_id, m.ts
            """,
            (desde.isoformat(), hasta.isoformat()),
        ).fetchall()

        bucket = defaultdict(lambda: defaultdict(list))
        for emp_id, ts, tipo in rows:
            dt = _parse_ts(ts)
            bucket[emp_id][dt.date()].append((tipo, dt))

        for emp_id, dias in bucket.items():
            for d, eventos in dias.items():
                # defaults por seguridad: nunca OK con NULL
                ent = None
                sal = None
                minutos = None
                estado = "REVISAR"
                detalle = None

                # Feriado: se paga 8h pero igual queda OK (solo OK/REVISAR)
                if _es_feriado(conn, d):
                    minutos = 8 * 60
                    estado = "OK"
                    detalle = "Feriado pago"
                    conn.execute(
                        """
                        INSERT INTO jornadas
                        (empleado_id, fecha, entrada_calc, salida_calc, minutos_calc, estado, detalle)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (emp_id, d.isoformat(), None, None, minutos, estado, detalle),
                    )
                    continue

                eventos_orden = sorted(eventos, key=lambda x: x[1])
                ents = [ts for tipo, ts in eventos_orden if tipo == "ENT"]
                sals = [ts for tipo, ts in eventos_orden if tipo == "SAL"]

                hi, hf, tol = _get_horario(conn, d)

                # 1) Horario partido (ENT,SAL,ENT,SAL)
                hp = _calc_horario_partido(eventos_orden, d, hi, hf, tol)
                if hp is not None:
                    ent, sal, minutos, detalle = hp
                    estado = "OK" if minutos is not None else "REVISAR"

                # 2) Caso normal: 1 ENT + 1 SAL
                elif len(ents) == 1 and len(sals) == 1:
                    ent = _clamp_entrada(ents[0], hi, tol)
                    sal = _clamp_salida(sals[0], hf)

                    if sal <= ent:
                        estado = "REVISAR"
                        minutos = None
                        detalle = "Salida anterior a entrada"
                    else:
                        minutos = int((sal - ent).total_seconds() // 60)
                        estado = "OK"
                        detalle = None

                # 3) Incompletas / múltiples
                else:
                    estado = "REVISAR"
                    minutos = None
                    detalle = _motivo_incompleto_o_multiple(len(ents), len(sals))

                # Control descanso: si está activado, se revisa aunque esté OK
                if estado == "OK" and _control_descanso(conn, emp_id):
                    estado = "REVISAR"
                    detalle = "Control de descanso: requiere verificación manual"

                # Guard final: nunca permitir OK con ent/sal None o minutos None
                if estado == "OK" and (minutos is None):
                    estado = "REVISAR"
                    if not detalle:
                        detalle = "No se pudo calcular minutos"
                if estado == "OK" and (ent is None or sal is None) and detalle != "Feriado pago":
                    estado = "REVISAR"
                    minutos = None
                    if not detalle:
                        detalle = "Par ENT/SAL inválido"

                conn.execute(
                    """
                    INSERT INTO jornadas
                    (empleado_id, fecha, entrada_calc, salida_calc, minutos_calc, estado, detalle)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        emp_id,
                        d.isoformat(),
                        ent.isoformat() if ent else None,
                        sal.isoformat() if sal else None,
                        minutos,
                        estado,
                        detalle,
                    ),
                )

        print("Jornadas calculadas.")
