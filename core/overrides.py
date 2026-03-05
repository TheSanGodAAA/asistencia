# core/overrides.py
from __future__ import annotations

from datetime import datetime, date


def _to_datetime_maybe_full(s: str, fecha_str: str) -> datetime:
    """Convierte una cadena que puede ser ISO completa o solo hora (HH:MM o HH:MM:SS)
    a un objeto datetime combinándolo con `fecha_str` cuando haga falta.
    """
    s = s.strip()
    
    # si ya incluye fecha (ej. '2025-12-01T08:00:00' o '2025-12-01 08:00:00')
    if "T" in s or (" " in s and len(s) > 10):
        # Normalizar: reemplazar espacio con 'T' para fromisoformat
        s_normalized = s.replace(" ", "T")
        return datetime.fromisoformat(s_normalized)

    # hora sola: aceptar 'HH:MM' o 'HH:MM:SS'
    fmt = "%H:%M:%S" if s.count(":") == 2 else "%H:%M"
    t = datetime.strptime(s, fmt).time()
    d = date.fromisoformat(fecha_str)
    return datetime.combine(d, t)


def aplicar_override(
    conn,
    jornada_id: int,
    entrada_iso: str,
    salida_iso: str,
    motivo: str,
) -> None:
    """
    Aplica corrección manual:
    - Guarda histórico en `jornadas_override` (guarda sólo la hora HH:MM:SS en los campos manuales)
    - Actualiza `jornadas`: `entrada_calc`/`salida_calc` se guardan como hora (HH:MM:SS),
      `minutos_calc` recalculado y `estado` puesto a 'OK'.
    Se aceptan entradas con fecha completa (ISO) o sólo hora.
    """
    # obtener fecha de la jornada para combinar en caso de hora sola
    row = conn.execute("SELECT fecha FROM jornadas WHERE id = ?", (jornada_id,)).fetchone()
    if not row:
        raise RuntimeError(f"Jornada {jornada_id} no encontrada")
    fecha_str = row[0]

    ent_dt = _to_datetime_maybe_full(entrada_iso, fecha_str)
    sal_dt = _to_datetime_maybe_full(salida_iso, fecha_str)
    if sal_dt <= ent_dt:
        raise ValueError("Salida <= Entrada")
    minutos = int((sal_dt - ent_dt).total_seconds() // 60)

    now = datetime.now().isoformat()

    # 1) Guardar override (histórico) - almacenamos sólo la hora para mayor legibilidad
    conn.execute(
        """
        INSERT INTO jornadas_override
        (jornada_id, entrada_manual, salida_manual, motivo, creado_en)
        VALUES (?, ?, ?, ?, ?)
        """,
        (jornada_id, ent_dt.time().isoformat(), sal_dt.time().isoformat(), motivo, now),
    )

    # 2) Actualizar la jornada: guardar horas (HH:MM:SS) en los campos calculados
    conn.execute(
        """
        UPDATE jornadas
        SET
            entrada_calc = ?,
            salida_calc  = ?,
            minutos_calc = ?,
            estado       = 'OK',
            detalle      = NULL
        WHERE id = ?
        """,
        (ent_dt.time().isoformat(), sal_dt.time().isoformat(), minutos, jornada_id),
    )
