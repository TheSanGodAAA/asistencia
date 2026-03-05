"""Script combinado para aplicar todos los overrides presentes en los distintos
scripts `ot*.py` en `db/`. Ejecuta en batch las correcciones definidas.

Uso: desde la raíz del proyecto:
    python db/apply_ot_all.py

El script ejecuta los siguientes lotes, en orden:
 - OT mass (como en `ot.py`): aplica una salida fija para todas las jornadas de una fecha
 - OT2: override puntual por `jornada_id` (si existe)
 - OT3 / OT4: listas de fixes por `(empleado_id, fecha, hin, hout)`
"""

import sys
from pathlib import Path

# Permitir ejecutar este script directamente: asegurar que la raíz del proyecto
# está en sys.path (evita ModuleNotFoundError cuando se ejecuta
# `python db/apply_ot_all.py`).
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import get_conn
from core.overrides import aplicar_override


def iso(fecha: str, hhmm: str) -> str:
    # Aceptar hhmm como "HH:MM" y devolver "HH:MM" (la función aplicar_override
    # acepta hora sola y la combina con la fecha internamente). Para mayor claridad
    # devolvemos hora sin fecha.
    return hhmm


def run_ot_mass(conn):
    # Basado en db/ot.py
    FECHA = "2025-12-13"
    SALIDA = "18:30"
    MOTIVO = "Corrección masiva 13/12/2025"

    rows = conn.execute(
        "SELECT id, empleado_id FROM jornadas WHERE fecha = ?",
        (FECHA,),
    ).fetchall()

    if not rows:
        print(f"[WARN] No hay jornadas para la fecha {FECHA}")
        return

    for jornada_id, emp_id in rows:
        entrada = "09:00" if emp_id == 3 else "08:00"
        try:
            aplicar_override(conn, jornada_id, entrada, SALIDA, MOTIVO)
            print(f"[OK] jornada_id={jornada_id} emp_id={emp_id}")
        except Exception as e:
            print(f"[ERROR] jornada_id={jornada_id} emp_id={emp_id}: {e}")


def run_ot2(conn):
    # Basado en db/ot2.py
    try:
        aplicar_override(
            conn,
            jornada_id=123,
            entrada_iso="2025-12-05T08:00:00",
            salida_iso="2025-12-05T17:30:00",
            motivo="Marcas múltiples corregidas",
        )
        print("[OK] OT2 aplicado (jornada_id=123)")
    except Exception as e:
        print(f"[ERROR] OT2: {e}")


def run_ot3(conn):
    # Basado en db/ot3.py
    MOTIVO = "Corrección manual: marcas múltiples (diciembre 2025)"

    FIXES = [
        (3,  "2025-12-05", "08:00", "17:30"),
        (5,  "2025-12-13", "08:00", "18:30"),
        (8,  "2025-12-03", "10:00", "18:30"),
        (8,  "2025-12-06", "08:00", "12:15"),
        (9,  "2025-12-12", "08:20", "17:30"),
        (11, "2025-12-12", "08:00", "17:30"),
        (15, "2025-12-02", "08:00", "18:30"),
        (15, "2025-12-09", "08:00", "18:30"),
        (17, "2025-12-08", "08:00", "17:30"),
    ]

    for emp_id, fecha, hin, hout in FIXES:
        row = conn.execute(
            "SELECT id, estado, detalle FROM jornadas WHERE empleado_id=? AND fecha=?",
            (emp_id, fecha),
        ).fetchone()

        if not row:
            print(f"[WARN] No existe jornada para empleado_id={emp_id} fecha={fecha}")
            continue

        jornada_id, estado_prev, detalle_prev = row

        try:
            aplicar_override(conn, jornada_id=jornada_id, entrada_iso=iso(fecha, hin), salida_iso=iso(fecha, hout), motivo=MOTIVO)
            print(f"[OK] emp_id={emp_id} {fecha} {hin}-{hout} (prev={estado_prev} / {detalle_prev})")
        except Exception as e:
            print(f"[ERROR] emp_id={emp_id} fecha={fecha}: {e}")


def run_ot4(conn):
    # Basado en db/ot4.py
    MOTIVO = "Corrección manual (batch REVISAR #1)"

    FIXES = [
        (2,  "2025-12-09", "08:00", "16:05"),
        (4,  "2025-12-06", "09:09", "18:30"),
        (6,  "2025-12-09", "08:00", "18:30"),
        (8,  "2025-12-04", "08:00", "18:30"),
        (9,  "2025-12-10", "08:00", "18:30"),
        (11, "2025-12-02", "08:00", "18:30"),
        (11, "2025-12-03", "08:00", "18:30"),
        (12, "2025-12-06", "08:00", "16:06"),
        (16, "2025-12-04", "08:00", "18:30"),
    ]

    def get_jornada_id(conn, empleado_id: int, fecha: str):
        row = conn.execute(
            "SELECT id FROM jornadas WHERE empleado_id=? AND fecha=?",
            (empleado_id, fecha),
        ).fetchone()
        return int(row[0]) if row else None

    for empleado_id, fecha, hin, hout in FIXES:
        jornada_id = get_jornada_id(conn, empleado_id, fecha)
        if jornada_id is None:
            print(f"[WARN] No existe jornada empleado_id={empleado_id} fecha={fecha}")
            continue

        ent = iso(fecha, hin)
        sal = iso(fecha, hout)

        try:
            aplicar_override(conn=conn, jornada_id=jornada_id, entrada_iso=ent, salida_iso=sal, motivo=MOTIVO)
            print(f"[OK] empleado_id={empleado_id} fecha={fecha} {hin}-{hout} (jornada_id={jornada_id})")
        except Exception as e:
            print(f"[ERROR] empleado_id={empleado_id} fecha={fecha}: {e}")


def main():
    with get_conn() as conn:
        print("== Ejecutando OT mass ==")
        run_ot_mass(conn)
        print("== Ejecutando OT2 ==")
        run_ot2(conn)
        print("== Ejecutando OT3 ==")
        run_ot3(conn)
        print("== Ejecutando OT4 ==")
        run_ot4(conn)


if __name__ == "__main__":
    main()
