from db.database import get_conn

TABLES_TO_CLEAR = [
    # detalles primero por claves foráneas
    "liquidacion_detalle",
    "liquidaciones",
    "jornadas_override",
    "jornadas",
    "marcaciones",
    "imports",
]

if __name__ == "__main__":
    with get_conn() as c:
        # por si hay FKs activas
        c.execute("PRAGMA foreign_keys = ON;")

        for t in TABLES_TO_CLEAR:
            c.execute(f"DELETE FROM {t};")

        # opcional: reset autoincrement (si te molesta que los IDs sigan)
        # Ojo: NO resetea empleados ni tarifas.
        c.execute("""
            DELETE FROM sqlite_sequence
            WHERE name IN ('imports','marcaciones','jornadas','jornadas_override','liquidaciones','liquidacion_detalle');
        """)

    print("Reset OK: imports/marcaciones/jornadas/overrides/liquidaciones vaciadas.")
