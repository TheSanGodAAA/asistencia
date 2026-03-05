"""Aplicar overrides listados por el usuario en batch.

Uso:
    python db/apply_ot_custom.py

El script busca la `jornada` correspondiente por `empleado_id` y `fecha`
y aplica `aplicar_override` guardando sólo las horas (`HH:MM:SS`).
"""

import sys
from pathlib import Path

# Asegurar que la raíz del proyecto está en sys.path para importar paquetes locales
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import get_conn
from core.overrides import aplicar_override


MOTIVO = "Overrides batch usuario (diciembre 2025)"

# Lista basada en la tabla proporcionada por el usuario
# Formato: (empleado_id, fecha, hora_entrada, hora_salida)
FIXES = [
    (1,  "2025-12-18", "8:00",  "18:30"),
    (2,  "2025-12-22", "9:00",  "17:30"),
    (4,  "2025-12-15", "8:00",  "18:30"),
    (4,  "2025-12-19", "8:00",  "18:30"),
    (4,  "2025-12-22", "8:00",  "18:30"),
    (6,  "2025-12-16", "8:09",  "18:30"),
    (7,  "2025-12-16", "8:07",  "17:30"),
    (11, "2025-12-17", "8:00",  "18:30"),
    (11, "2025-12-20", "8:00",  "18:30"),
    (16, "2025-12-15", "11:00", "18:30"),
]


def normalize_time(h: str) -> str:
    """Normaliza horas como '8:00' -> '08:00' y devuelve 'HH:MM'."""
    parts = h.split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 and parts[1] != "" else 0
    return f"{hour:02d}:{minute:02d}"


def get_jornada_id(conn, empleado_id: int, fecha: str):
    row = conn.execute(
        "SELECT id FROM jornadas WHERE empleado_id=? AND fecha=?",
        (empleado_id, fecha),
    ).fetchone()
    return int(row[0]) if row else None


def main():
    with get_conn() as conn:
        for empleado_id, fecha, hin, hout in FIXES:
            jornada_id = get_jornada_id(conn, empleado_id, fecha)
            if jornada_id is None:
                print(f"[WARN] No existe jornada empleado_id={empleado_id} fecha={fecha}")
                continue

            ent = normalize_time(hin)
            sal = normalize_time(hout)

            try:
                aplicar_override(conn=conn, jornada_id=jornada_id, entrada_iso=ent, salida_iso=sal, motivo=MOTIVO)
                print(f"[OK] empleado_id={empleado_id} fecha={fecha} {ent}-{sal} (jornada_id={jornada_id})")
            except Exception as e:
                print(f"[ERROR] empleado_id={empleado_id} fecha={fecha}: {e}")


if __name__ == "__main__":
    main()
