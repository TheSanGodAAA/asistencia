from datetime import date

from core.jornadas import calcular_jornadas


def calcular_jornadas_rango(desde: date, hasta: date) -> None:
    """Calcula jornadas para un rango de fechas inclusive."""
    if hasta < desde:
        raise ValueError("Rango inválido: 'hasta' no puede ser menor que 'desde'")
    calcular_jornadas(desde, hasta)
