"""Exportar liquidación procesada a TXT y XLSX.

Columnas de salida:
    ID | Nombre | HorasTrabajadas | Monto(antes de vale) | Vales | MontoFinal(luego de vales)

Uso:
    python db/export_processed.py <anio> <mes>
"""

import sys
from pathlib import Path

# Asegurar imports locales
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.report_service import export_liquidacion_txt_xlsx


def main():
    if len(sys.argv) < 3:
        print("Usage: python db/export_processed.py <anio> <mes>")
        sys.exit(1)

    anio = int(sys.argv[1])
    mes = int(sys.argv[2])

    out_dir = PROJECT_ROOT / "data" / "processed"
    try:
        out_txt, out_xlsx = export_liquidacion_txt_xlsx(anio, mes, out_dir=out_dir)
    except RuntimeError as e:
        print(str(e))
        sys.exit(1)

    print(f"Export TXT generado: {out_txt}")
    print(f"Export XLSX generado: {out_xlsx}")


if __name__ == "__main__":
    main()
