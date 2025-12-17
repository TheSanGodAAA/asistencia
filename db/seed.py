from datetime import date
from db.database import get_conn

def seed_horario():
    with get_conn() as conn:
        # Horario normal histórico (si querés conservarlo)
        conn.execute(
            """
            INSERT OR IGNORE INTO horarios_vigencia
            (desde, hora_inicio, hora_fin, tolerancia_min, nota)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("2025-01-01", "08:00", "17:30", 5, "Horario normal")
        )

        # Horario actual (temporada)
        conn.execute(
            """
            INSERT OR IGNORE INTO horarios_vigencia
            (desde, hora_inicio, hora_fin, tolerancia_min, nota)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("2025-12-01", "08:00", "18:30", 5, "Horario actual/temporada")
        )

def seed_feriados():
    feriados = [
        ("2025-01-01", "Año Nuevo", 8),
        ("2025-05-01", "Día del Trabajador", 8),
        ("2025-07-18", "Jura de la Constitución", 8),
        ("2025-08-25", "Declaratoria de la Independencia", 8),
        ("2025-12-25", "Navidad", 8),
    ]
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO feriados
            (fecha, nombre, horas_pagas)
            VALUES (?, ?, ?)
            """,
            feriados
        )

if __name__ == "__main__":
    seed_horario()
    seed_feriados()
    print("Datos base cargados.")
