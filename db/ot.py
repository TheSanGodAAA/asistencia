# db/ot_masivo_1312.py
from core.overrides import aplicar_override
from db.database import get_conn

FECHA = "2025-12-13"
SALIDA = f"{FECHA}T18:30:00"
MOTIVO = "Corrección masiva 13/12/2025"

if __name__ == "__main__":
    with get_conn() as c:
        jornadas = c.execute(
            "SELECT id, empleado_id FROM jornadas WHERE fecha=?",
            (FECHA,),
        ).fetchall()

        if not jornadas:
            raise RuntimeError("No hay jornadas para esa fecha")

        for jornada_id, emp_id in jornadas:
            entrada = f"{FECHA}T{'09:00' if emp_id == 3 else '08:00'}:00"
            aplicar_override(c, jornada_id, entrada, SALIDA, MOTIVO)
            print(f"[OK] jornada_id={jornada_id} emp_id={emp_id}")

    print("Overrides aplicados correctamente.")
