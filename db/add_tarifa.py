"""Agregar una tarifa para un empleado.

Ejemplos:
  python db/add_tarifa.py --ac_no 22 --pago 178.61 --nombre Veronica
  python db/add_tarifa.py --empleado_id 18 --pago 178.61

El script crea el empleado si no existe (cuando se pasa `--ac_no`) y
inserta una fila en `tarifas_empleado` con `desde` por defecto '2025-12-01'.
"""

import sys
from pathlib import Path
import argparse
from datetime import date

# Asegurar import local
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import get_conn


DEFAULT_DESDE = "2025-12-01"


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ac_no", type=int, help="AC no. del empleado (ej. 22)")
    g.add_argument("--empleado_id", type=int, help="ID interno del empleado")
    p.add_argument("--pago", type=float, required=True, help="Pago por hora en UYU, p.ej. 178.61")
    p.add_argument("--desde", default=DEFAULT_DESDE, help="Fecha desde (YYYY-MM-DD)")
    p.add_argument("--nombre", default=None, help="Nombre del empleado si se crea")
    args = p.parse_args()

    pago_hora_cent = int(round(args.pago * 100))

    with get_conn() as conn:
        empleado_id = None
        if args.empleado_id:
            row = conn.execute("SELECT id, ac_no, nombre FROM empleados WHERE id = ?", (args.empleado_id,)).fetchone()
            if not row:
                raise RuntimeError(f"No existe empleado con id={args.empleado_id}")
            empleado_id = row[0]
        else:
            # buscar por ac_no
            row = conn.execute("SELECT id, nombre FROM empleados WHERE ac_no = ?", (args.ac_no,)).fetchone()
            if row:
                empleado_id = row[0]
            else:
                nombre = args.nombre if args.nombre else f"Empleado {args.ac_no}"
                cur = conn.execute("INSERT INTO empleados (ac_no, nombre) VALUES (?, ?)", (args.ac_no, nombre))
                empleado_id = cur.lastrowid
                print(f"Creado empleado id={empleado_id} ac_no={args.ac_no} nombre={nombre}")

        conn.execute(
            """
            INSERT INTO tarifas_empleado (empleado_id, desde, pago_hora_cent, nota)
            VALUES (?, ?, ?, ?)
            """,
            (empleado_id, args.desde, pago_hora_cent, f"Alta manual {date.today().isoformat()}"),
        )

        print(f"Tarifa agregada: empleado_id={empleado_id} pago_hora_cent={pago_hora_cent} (UYU {args.pago}) desde={args.desde}")


if __name__ == "__main__":
    main()
