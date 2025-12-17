# db/ot_uno.py
from core.overrides import aplicar_override
from db.database import get_conn

if __name__ == "__main__":
    with get_conn() as c:
        aplicar_override(
            c,
            jornada_id=123,
            entrada_iso="2025-12-05T08:00:00",
            salida_iso="2025-12-05T17:30:00",
            motivo="Marcas múltiples corregidas",
        )
    print("OK")
