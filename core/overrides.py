# core/overrides.py
from __future__ import annotations

from datetime import datetime

def _minutos_entre(ent_iso: str, sal_iso: str) -> int:
    ent = datetime.fromisoformat(ent_iso)
    sal = datetime.fromisoformat(sal_iso)
    if sal <= ent:
        raise ValueError("Salida <= Entrada")
    return int((sal - ent).total_seconds() // 60)

def aplicar_override(
    conn,
    jornada_id: int,
    entrada_iso: str,
    salida_iso: str,
    motivo: str,
) -> None:
    """
    Aplica corrección manual:
    - Guarda histórico en jornadas_override (una fila por aplicación)
    - Actualiza jornadas: entrada_calc/salida_calc/minutos_calc + estado OK (detalle NULL)
    """
    minutos = _minutos_entre(entrada_iso, salida_iso)
    now = datetime.now().isoformat()

    # 1) Guardar override (histórico)
    conn.execute(
        """
        INSERT INTO jornadas_override
        (jornada_id, entrada_manual, salida_manual, motivo, creado_en)
        VALUES (?, ?, ?, ?, ?)
        """,
        (jornada_id, entrada_iso, salida_iso, motivo, now),
    )

    # 2) Pisar la jornada (esto te faltaba para que NO quede NULL)
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
        (entrada_iso, salida_iso, minutos, jornada_id),
    )
