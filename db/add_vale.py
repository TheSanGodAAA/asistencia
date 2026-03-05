"""Registrar un vale (adelanto) para un empleado.

Ejemplos:
  python db/add_vale.py --ac_no 5 --monto 2500 --fecha 2026-02-10 --nota "Vale caja"
  python db/add_vale.py --empleado_id 3 --monto 1200

`monto` se expresa en UYU y se guarda en centavos.
"""

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import get_conn


def ensure_vales_schema(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vales (
          id            INTEGER PRIMARY KEY AUTOINCREMENT,
          empleado_id   INTEGER NOT NULL,
          fecha         TEXT    NOT NULL,
          monto_cent    INTEGER NOT NULL CHECK(monto_cent >= 0),
          nota          TEXT,
                    es_arrastre   INTEGER NOT NULL DEFAULT 0,
                    origen_anio   INTEGER,
                    origen_mes    INTEGER,
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
        conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_vales_arrastre_origen
                    ON vales(es_arrastre, origen_anio, origen_mes)
                """
        )


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ac_no", type=int, help="AC no. del empleado")
    g.add_argument("--empleado_id", type=int, help="ID interno del empleado")
    p.add_argument("--monto", type=float, required=True, help="Monto del vale en UYU")
    p.add_argument("--fecha", default=date.today().isoformat(), help="Fecha del vale (YYYY-MM-DD)")
    p.add_argument("--nota", default="", help="Nota opcional")
    args = p.parse_args()

    if args.monto < 0:
        raise ValueError("El monto no puede ser negativo")

    monto_cent = int(round(args.monto * 100))

    with get_conn() as conn:
        ensure_vales_schema(conn)

        if args.empleado_id is not None:
            row = conn.execute("SELECT id, nombre FROM empleados WHERE id = ?", (args.empleado_id,)).fetchone()
        else:
            row = conn.execute("SELECT id, nombre FROM empleados WHERE ac_no = ?", (args.ac_no,)).fetchone()

        if not row:
            raise RuntimeError("Empleado no encontrado")

        empleado_id, nombre = int(row[0]), row[1]

        conn.execute(
            """
            INSERT INTO vales (empleado_id, fecha, monto_cent, nota, creado_en)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                empleado_id,
                args.fecha,
                monto_cent,
                args.nota,
                datetime.now().isoformat(),
            ),
        )

    print(
        f"Vale registrado: empleado_id={empleado_id} nombre={nombre} "
        f"fecha={args.fecha} monto={args.monto:.2f} UYU"
    )


if __name__ == "__main__":
    main()
