# db/ot_fixes.py
from core.overrides import aplicar_override
from db.database import get_conn

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

def iso(fecha: str, hhmm: str) -> str:
    return f"{fecha}T{hhmm}:00"

if __name__ == "__main__":
    with get_conn() as c:
        for emp_id, fecha, hin, hout in FIXES:
            row = c.execute(
                "SELECT id, estado, detalle FROM jornadas WHERE empleado_id=? AND fecha=?",
                (emp_id, fecha),
            ).fetchone()

            if not row:
                print(f"[WARN] No existe jornada para empleado_id={emp_id} fecha={fecha}")
                continue

            jornada_id, estado_prev, detalle_prev = row

            aplicar_override(
                c,
                jornada_id=jornada_id,
                entrada_iso=iso(fecha, hin),
                salida_iso=iso(fecha, hout),
                motivo=MOTIVO,
            )

            print(f"[OK] emp_id={emp_id} {fecha} {hin}-{hout} (prev={estado_prev} / {detalle_prev})")

    print("Listo.")
