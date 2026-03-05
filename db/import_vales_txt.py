"""Importar vales desde TXT con formato: ID Dinero Fecha.

Formato esperado por línea:
  <empleado_id> <monto_sin_decimales> <dd/mm/yyyy>

También soporta separador por tabulaciones.
Ignora encabezados y líneas vacías.

Uso:
  python db/import_vales_txt.py data/vales/raw/02-2026.txt
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import get_conn
from core.liquidacion import _ensure_vales_schema


def _parse_fecha(s: str) -> str:
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"Fecha invalida: {s}")


def _parse_line(line: str) -> tuple[int, int, str] | None:
    raw = line.strip()
    if not raw:
        return None

    low = raw.lower()
    if low.startswith("id") or "dinero" in low and "fecha" in low:
        return None

    parts = raw.replace("\t", " ").split()
    if len(parts) != 3:
        raise ValueError(f"Formato invalido: {line.rstrip()}")

    empleado_id = int(parts[0])
    monto_cent = int(parts[1]) * 100
    fecha_iso = _parse_fecha(parts[2])

    if monto_cent < 0:
        raise ValueError("Monto negativo no permitido")

    return empleado_id, monto_cent, fecha_iso


def import_txt(path: Path) -> tuple[int, int]:
    inserted = 0
    skipped = 0
    now = datetime.now().isoformat()

    with get_conn() as conn:
        _ensure_vales_schema(conn)

        with path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                parsed = _parse_line(line)
                if parsed is None:
                    continue

                empleado_id, monto_cent, fecha_iso = parsed

                emp = conn.execute(
                    "SELECT 1 FROM empleados WHERE id = ?",
                    (empleado_id,),
                ).fetchone()
                if not emp:
                    raise RuntimeError(f"Linea {i}: empleado_id {empleado_id} no existe")

                exists = conn.execute(
                    """
                    SELECT 1 FROM vales
                    WHERE empleado_id = ? AND fecha = ? AND monto_cent = ?
                    LIMIT 1
                    """,
                    (empleado_id, fecha_iso, monto_cent),
                ).fetchone()
                if exists:
                    skipped += 1
                    continue

                conn.execute(
                    """
                    INSERT INTO vales (empleado_id, fecha, monto_cent, nota, creado_en)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (empleado_id, fecha_iso, monto_cent, f"Importado desde {path.name}", now),
                )
                inserted += 1

    return inserted, skipped


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("path", help="Ruta al txt de vales")
    args = p.parse_args()

    path = Path(args.path)
    if not path.exists():
        raise FileNotFoundError(f"No existe archivo: {path}")

    inserted, skipped = import_txt(path)
    print(f"Vales importados: {inserted} | Duplicados omitidos: {skipped}")


if __name__ == "__main__":
    main()
