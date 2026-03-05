import argparse
from datetime import date

from pathlib import Path
import sys

from core.logger import get_logger
from services.import_service import import_marcaciones_from_txt
from services.jornadas_service import calcular_jornadas_rango
from services.liquidacion_service import crear_liquidacion_borrador, cerrar_liquidacion_mensual

logger = get_logger(__name__)


def _parse_yyyy_mm_dd(s: str) -> date:
    y, m, d = map(int, s.split("-"))
    return date(y, m, d)


def cmd_import(args):
    try:
        logger.info(f"Importando archivo: {args.path}")
        path = Path(args.path)
        if not path.exists():
            logger.error(f"Archivo no encontrado: {path}")
            sys.exit(1)
        parsed = import_marcaciones_from_txt(path)
        logger.info(f"Registros parseados: {parsed}")
        logger.info("Importación completada exitosamente.")
    except Exception as e:
        logger.error(f"Error durante importación: {e}", exc_info=True)
        sys.exit(1)


def cmd_jornadas(args):
    try:
        logger.info(f"Calculando jornadas: {args.desde} hasta {args.hasta}")
        desde = _parse_yyyy_mm_dd(args.desde)
        hasta = _parse_yyyy_mm_dd(args.hasta)
        calcular_jornadas_rango(desde, hasta)
        logger.info("Jornadas calculadas exitosamente.")
    except Exception as e:
        logger.error(f"Error al calcular jornadas: {e}", exc_info=True)
        sys.exit(1)


def cmd_liquidar(args):
    try:
        logger.info(f"Creando liquidación borrador: {args.anio}-{args.mes:02d}")
        lid = crear_liquidacion_borrador(args.anio, args.mes)
        logger.info(f"Liquidación borrador creada con id={lid}")
        print(f"✓ Liquidación borrador id: {lid}")
    except Exception as e:
        logger.error(f"Error al crear liquidación: {e}", exc_info=True)
        sys.exit(1)


def cmd_cerrar(args):
    try:
        logger.info(f"Cerrando liquidación: {args.anio}-{args.mes:02d}")
        cerrar_liquidacion_mensual(args.anio, args.mes)
        logger.info(f"Liquidación cerrada: {args.anio}-{args.mes:02d}")
        print(f"✓ Liquidación CERRADA: {args.anio}-{args.mes:02d}")
    except Exception as e:
        logger.error(f"Error al cerrar liquidación: {e}", exc_info=True)
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(prog="asistencia")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_import = sub.add_parser("import", help="Importar TXT a marcaciones")
    p_import.add_argument("path", help="Ruta al archivo .txt")
    p_import.set_defaults(func=cmd_import)

    p_j = sub.add_parser("jornadas", help="Calcular jornadas desde marcaciones")
    p_j.add_argument("desde", help="YYYY-MM-DD")
    p_j.add_argument("hasta", help="YYYY-MM-DD")
    p_j.set_defaults(func=cmd_jornadas)

    p_l = sub.add_parser("liquidar", help="Crear borrador de liquidación")
    p_l.add_argument("anio", type=int)
    p_l.add_argument("mes", type=int)
    p_l.set_defaults(func=cmd_liquidar)

    p_c = sub.add_parser("cerrar", help="Cerrar liquidación")
    p_c.add_argument("anio", type=int)
    p_c.add_argument("mes", type=int)
    p_c.set_defaults(func=cmd_cerrar)

    try:
        args = p.parse_args()
        args.func(args)
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
