"""Actualizar el nombre de un empleado por `ac_no` o `empleado_id`.

Uso:
  python db/update_employee_name.py --ac_no 22 --nombre Veronica
  python db/update_employee_name.py --empleado_id 18 --nombre Veronica
"""

import sys
from pathlib import Path
import argparse

# Asegurar imports locales
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import get_conn


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ac_no", type=int, help="AC number del empleado")
    g.add_argument("--empleado_id", type=int, help="ID interno del empleado")
    p.add_argument("--nombre", required=True, help="Nuevo nombre a establecer")
    args = p.parse_args()

    with get_conn() as conn:
        if args.ac_no:
            row = conn.execute("SELECT id, nombre FROM empleados WHERE ac_no = ?", (args.ac_no,)).fetchone()
            if not row:
                print(f"No existe empleado con ac_no={args.ac_no}")
                return
            empleado_id = row[0]
        else:
            row = conn.execute("SELECT id, nombre FROM empleados WHERE id = ?", (args.empleado_id,)).fetchone()
            if not row:
                print(f"No existe empleado con id={args.empleado_id}")
                return
            empleado_id = row[0]

        conn.execute("UPDATE empleados SET nombre = ? WHERE id = ?", (args.nombre, empleado_id))
        print(f"Empleado actualizado: id={empleado_id} nombre={args.nombre}")


if __name__ == "__main__":
    main()
