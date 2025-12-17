import argparse
from datetime import date

from pathlib import Path

from core.parser import parse_file
from core.importer import import_txt
from core.jornadas import calcular_jornadas
from core.liquidacion import crear_borrador_liquidacion, cerrar_liquidacion


def _parse_yyyy_mm_dd(s: str) -> date:
    y, m, d = map(int, s.split("-"))
    return date(y, m, d)


def cmd_import(args):
    path = Path(args.path)
    records = list(parse_file(path))
    import_txt(path, records)


def cmd_jornadas(args):
    desde = _parse_yyyy_mm_dd(args.desde)
    hasta = _parse_yyyy_mm_dd(args.hasta)
    calcular_jornadas(desde, hasta)


def cmd_liquidar(args):
    lid = crear_borrador_liquidacion(args.anio, args.mes)
    print("Liquidación borrador id:", lid)


def cmd_cerrar(args):
    cerrar_liquidacion(args.anio, args.mes)
    print("Liquidación CERRADA.")


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

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
