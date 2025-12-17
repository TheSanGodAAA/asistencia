from db.database import get_conn
from core.overrides import aplicar_override

MOTIVO = "Corrección manual (batch REVISAR #1)"

# En el mismo orden que tu screenshot (9 filas) + tu lista (9 horarios)
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

def iso(fecha: str, hhmm: str) -> str:
    # hhmm esperado: "HH:MM"
    return f"{fecha}T{hhmm}:00"

def get_jornada_id(conn, empleado_id: int, fecha: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM jornadas WHERE empleado_id=? AND fecha=?",
        (empleado_id, fecha),
    ).fetchone()
    return int(row[0]) if row else None

if __name__ == "__main__":
    with get_conn() as c:
        for empleado_id, fecha, hin, hout in FIXES:
            jornada_id = get_jornada_id(c, empleado_id, fecha)
            if jornada_id is None:
                print(f"[WARN] No existe jornada empleado_id={empleado_id} fecha={fecha}")
                continue

            ent_iso = iso(fecha, hin)
            sal_iso = iso(fecha, hout)

            # Validaciones rápidas
            if not isinstance(ent_iso, str) or not isinstance(sal_iso, str):
                raise TypeError(f"ISO inválido: ent={ent_iso!r} sal={sal_iso!r}")
            if len(ent_iso) < 16 or len(sal_iso) < 16:
                raise ValueError(f"ISO mal formado: ent={ent_iso!r} sal={sal_iso!r}")

            aplicar_override(
                conn=c,
                jornada_id=jornada_id,
                entrada_iso=ent_iso,
                salida_iso=sal_iso,
                motivo=MOTIVO,
            )

            print(f"[OK] empleado_id={empleado_id} fecha={fecha} {hin}-{hout} (jornada_id={jornada_id})")

    print("Listo.")
