from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re

from db.database import get_conn


def file_hash(path: Path) -> str:
    h = sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def get_or_create_empleado(conn, ac_no: int) -> int:
    row = conn.execute("SELECT id FROM empleados WHERE ac_no = ?", (ac_no,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO empleados (ac_no, nombre) VALUES (?, ?)",
        (ac_no, f"Empleado {ac_no}"),
    )
    return cur.lastrowid


def import_txt(path: Path, records):
    h = file_hash(path)

    with get_conn() as conn:
        # evitar importar dos veces el mismo archivo
        row = conn.execute("SELECT id FROM imports WHERE hash = ?", (h,)).fetchone()
        if row:
            print("Archivo ya importado. Se omite.")
            return

        cur = conn.execute(
            """
            INSERT INTO imports (archivo_nombre, hash, importado_en)
            VALUES (?, ?, ?)
            """,
            (path.name, h, datetime.now().isoformat()),
        )
        import_id = cur.lastrowid

        for r in records:
            empleado_id = get_or_create_empleado(conn, int(r["ac_no"]))

            # r["ts"] puede venir como datetime o como str ISO, soportamos ambos
            ts = r["ts"]
            ts_iso = ts.isoformat(timespec="seconds") if hasattr(ts, "isoformat") else str(ts)

            conn.execute(
                """
                INSERT INTO marcaciones
                (empleado_id, ts, tipo, import_id, raw_line)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    empleado_id,
                    ts_iso,
                    r["tipo"],               # "ENT" o "SAL"
                    import_id,
                    r.get("raw", ""),        # raw opcional
                ),
            )

    print("Importación completada.")
