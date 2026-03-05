from core.liquidacion import crear_borrador_liquidacion, cerrar_liquidacion


def crear_liquidacion_borrador(anio: int, mes: int) -> int:
    """Crea o recalcula una liquidación mensual en estado BORRADOR."""
    if mes < 1 or mes > 12:
        raise ValueError("Mes inválido: debe estar entre 1 y 12")
    return crear_borrador_liquidacion(anio, mes)


def cerrar_liquidacion_mensual(anio: int, mes: int) -> None:
    """Cierra una liquidación mensual existente."""
    if mes < 1 or mes > 12:
        raise ValueError("Mes inválido: debe estar entre 1 y 12")
    cerrar_liquidacion(anio, mes)
