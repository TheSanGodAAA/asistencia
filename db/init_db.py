from pathlib import Path
from db.database import get_conn, PROJECT_ROOT

def init_db() -> None:
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    schema = schema_path.read_text(encoding="utf-8")

    with get_conn() as conn:
        conn.executescript(schema)

if __name__ == "__main__":
    init_db()
    print("DB inicializada correctamente.")
    print(f"Ruta: {PROJECT_ROOT / 'asistencia.db'}")
