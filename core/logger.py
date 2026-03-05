"""Logging centralizado para el proyecto asistencia."""

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Configurar logger raíz
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGS_DIR / "asistencia.log"),
    ],
)

def get_logger(name: str) -> logging.Logger:
    """Obtener un logger con el nombre especificado."""
    return logging.getLogger(name)
