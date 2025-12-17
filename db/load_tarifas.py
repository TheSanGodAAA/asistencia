import csv
from pathlib import Path
from db.database import get_conn

DESDE = "2025-12-01"
CSV_PATH = Path("data") / "tarifas_2025-12-01.csv"

def main():
    with get_conn() as conn, open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ac_no = int(row["ac_no"])
            pago_hora_uyu = float(row["pago_hora_uyu"])
            pago_hora_cent = int(round(pago_hora_uyu * 100))

            emp = conn.execute("SELECT id FROM empleados WHERE ac_no = ?", (ac_no,)).fetchone()
            if not emp:
                raise RuntimeError(f"No existe empleado con ac_no={ac_no} en empleados")

            empleado_id = emp[0]
            conn.execute(
                """
                INSERT INTO tarifas_empleado (empleado_id, desde, pago_hora_cent, nota)
                VALUES (?, ?, ?, ?)
                """,
                (empleado_id, DESDE, pago_hora_cent, "Carga inicial diciembre 2025")
            )

    print("Tarifas cargadas OK.")

if __name__ == "__main__":
    main()
