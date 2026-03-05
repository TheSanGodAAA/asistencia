from pathlib import Path

from core.importer import import_txt
from core.parser import parse_file


def import_marcaciones_from_txt(path: str | Path) -> int:
    """Importa marcaciones desde un TXT.

    Retorna la cantidad de registros parseados (antes de deduplicación por hash de archivo).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {p}")

    records = list(parse_file(p))
    import_txt(p, records)
    return len(records)
