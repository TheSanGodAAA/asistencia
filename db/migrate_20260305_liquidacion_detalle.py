"""Migracion 2026-03-05: normalizar liquidacion_detalle al esquema final.

Esquema objetivo:
  id, liquidacion_id, empleado_id, minutos_pagados, pago_hora_cent,
  monto_cent, vales_cent, monto_final_cent

La migracion es idempotente: si el esquema ya coincide, no hace cambios.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import get_conn


EXPECTED = [
    "id",
    "liquidacion_id",
    "empleado_id",
    "minutos_pagados",
    "pago_hora_cent",
    "monto_cent",
    "vales_cent",
    "monto_final_cent",
]


def main() -> None:
    with get_conn() as conn:
        table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='liquidacion_detalle'"
        ).fetchone()

        if not table_exists:
            conn.execute(
                """
                CREATE TABLE liquidacion_detalle (
                  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                  liquidacion_id     INTEGER NOT NULL,
                  empleado_id        INTEGER NOT NULL,
                  minutos_pagados    INTEGER NOT NULL,
                  pago_hora_cent     INTEGER NOT NULL,
                  monto_cent         INTEGER NOT NULL,
                  vales_cent         INTEGER NOT NULL DEFAULT 0,
                  monto_final_cent   INTEGER NOT NULL,
                  FOREIGN KEY (liquidacion_id) REFERENCES liquidaciones(id) ON DELETE CASCADE,
                  FOREIGN KEY (empleado_id) REFERENCES empleados(id),
                  UNIQUE (liquidacion_id, empleado_id)
                )
                """
            )
            print("Tabla liquidacion_detalle creada con esquema final.")
            return

        cols = [r[1] for r in conn.execute("PRAGMA table_info(liquidacion_detalle)").fetchall()]
        if cols == EXPECTED:
            print("Schema ya actualizado. Sin cambios.")
            return

        old_cols = set(cols)
        monto_src = "monto_cent"
        if "monto_bruto_cent" in old_cols:
            monto_src = "COALESCE(monto_bruto_cent, monto_cent)"

        vales_src = "0"
        if "vales_cent" in old_cols:
            vales_src = "COALESCE(vales_cent, 0)"
        elif "vales_mes_cent" in old_cols:
            vales_src = "COALESCE(vales_mes_cent, 0)"

        final_src = "monto_cent"
        if "monto_final_cent" in old_cols:
            final_src = "COALESCE(monto_final_cent, monto_cent)"
        elif "monto_neto_cent" in old_cols:
            final_src = "COALESCE(monto_neto_cent, monto_cent)"

        conn.execute(
            """
            CREATE TABLE liquidacion_detalle_new (
              id                 INTEGER PRIMARY KEY AUTOINCREMENT,
              liquidacion_id     INTEGER NOT NULL,
              empleado_id        INTEGER NOT NULL,
              minutos_pagados    INTEGER NOT NULL,
              pago_hora_cent     INTEGER NOT NULL,
              monto_cent         INTEGER NOT NULL,
              vales_cent         INTEGER NOT NULL DEFAULT 0,
              monto_final_cent   INTEGER NOT NULL,
              FOREIGN KEY (liquidacion_id) REFERENCES liquidaciones(id) ON DELETE CASCADE,
              FOREIGN KEY (empleado_id) REFERENCES empleados(id),
              UNIQUE (liquidacion_id, empleado_id)
            )
            """
        )

        conn.execute(
            f"""
            INSERT INTO liquidacion_detalle_new
            (id, liquidacion_id, empleado_id, minutos_pagados, pago_hora_cent, monto_cent, vales_cent, monto_final_cent)
            SELECT id, liquidacion_id, empleado_id, minutos_pagados, pago_hora_cent,
                   {monto_src}, {vales_src}, {final_src}
            FROM liquidacion_detalle
            """
        )

        conn.execute("DROP TABLE liquidacion_detalle")
        conn.execute("ALTER TABLE liquidacion_detalle_new RENAME TO liquidacion_detalle")
        print("Schema liquidacion_detalle migrado correctamente.")


if __name__ == "__main__":
    main()
