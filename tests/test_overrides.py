"""Tests para core/overrides.py"""

import pytest
from pathlib import Path
import tempfile
import sys
from datetime import date, datetime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import get_conn_ctx
from core.overrides import aplicar_override, _to_datetime_maybe_full
from db.init_db import init_db


@pytest.fixture(scope="function")
def temp_db():
    """Crear una DB temporal para tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    import db.database as db_mod
    original_db_path = db_mod.DB_PATH
    db_mod.DB_PATH = Path(db_path)
    
    init_db()
    
    yield Path(db_path)
    
    db_mod.DB_PATH = original_db_path
    
    # Cleanup WAL files on Windows
    import time
    time.sleep(0.1)  # Brief delay for DB to fully close
    for suffix in ['', '-wal', '-shm']:
        try:
            Path(db_path + suffix).unlink(missing_ok=True)
        except:
            pass


@pytest.fixture
def sample_override_data(temp_db):
    """Crear empleados y jornadas para tests de override."""
    with get_conn_ctx() as conn:
        conn.execute("INSERT INTO empleados (ac_no, nombre) VALUES (1, 'Juan')")
        emp_id = conn.execute("SELECT id FROM empleados WHERE ac_no=1").fetchone()[0]
        
        # jornada REVISAR
        conn.execute(
            """
            INSERT INTO jornadas (empleado_id, fecha, entrada_calc, salida_calc, minutos_calc, estado, detalle)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (emp_id, "2025-12-01", "08:00:00", "17:30:00", 570, "REVISAR", "Marcas múltiples"),
        )
    
    return temp_db


class TestToDatetimeMaybeFull:
    """Test de conversión de strings a datetime."""

    def test_iso_completo(self):
        """Parseaar ISO completo."""
        dt = _to_datetime_maybe_full("2025-12-01T08:30:00", "2025-12-01")
        assert dt.year == 2025
        assert dt.month == 12
        assert dt.day == 1
        assert dt.hour == 8
        assert dt.minute == 30

    def test_hora_sola_hhmm(self):
        """Parsear hora sola HH:MM."""
        dt = _to_datetime_maybe_full("08:30", "2025-12-01")
        assert dt.year == 2025
        assert dt.month == 12
        assert dt.day == 1
        assert dt.hour == 8
        assert dt.minute == 30

    def test_hora_sola_hhmmss(self):
        """Parsear hora sola HH:MM:SS."""
        dt = _to_datetime_maybe_full("08:30:45", "2025-12-01")
        assert dt.year == 2025
        assert dt.month == 12
        assert dt.day == 1
        assert dt.hour == 8
        assert dt.minute == 30
        assert dt.second == 45

    def test_iso_con_espacios(self):
        """Parsear ISO con espacios."""
        dt = _to_datetime_maybe_full("2025-12-01 08:30:00", "2025-12-01")
        assert dt.hour == 8
        assert dt.minute == 30


class TestAplicarOverride:
    """Test de aplicación de overrides."""

    def test_aplicar_override_hora_sola(self, sample_override_data):
        """Aplicar override con horas solas."""
        with get_conn_ctx() as conn:
            jornada_id = conn.execute(
                "SELECT id FROM jornadas WHERE empleado_id=1 AND fecha=?"
                , ("2025-12-01",)
            ).fetchone()[0]
            
            aplicar_override(conn, jornada_id, "08:00", "17:30", "Corrección manual")
        
        with get_conn_ctx() as conn:
            jornada = conn.execute(
                "SELECT entrada_calc, salida_calc, minutos_calc, estado FROM jornadas WHERE id=?",
                (jornada_id,),
            ).fetchone()
        
        assert jornada[0] == "08:00:00"
        assert jornada[1] == "17:30:00"
        assert jornada[2] == 570  # 9.5 horas
        assert jornada[3] == "OK"

    def test_aplicar_override_iso_completo(self, sample_override_data):
        """Aplicar override con ISO completo."""
        with get_conn_ctx() as conn:
            jornada_id = conn.execute(
                "SELECT id FROM jornadas WHERE empleado_id=1 AND fecha=?",
                ("2025-12-01",),
            ).fetchone()[0]
            
            aplicar_override(
                conn, jornada_id,
                "2025-12-01T08:15:00",
                "2025-12-01T17:45:00",
                "Ajuste"
            )
        
        with get_conn_ctx() as conn:
            jornada = conn.execute(
                "SELECT minutos_calc FROM jornadas WHERE id=?",
                (jornada_id,),
            ).fetchone()
        
        # 08:15 a 17:45 = 570 min (9.5h)
        assert jornada[0] == 570

    def test_aplicar_override_guarda_historico(self, sample_override_data):
        """Aplicar override → se guarda histórico."""
        with get_conn_ctx() as conn:
            jornada_id = conn.execute(
                "SELECT id FROM jornadas WHERE empleado_id=1 AND fecha=?",
                ("2025-12-01",),
            ).fetchone()[0]
            
            aplicar_override(conn, jornada_id, "08:30", "17:00", "Prueba")
        
        with get_conn_ctx() as conn:
            override = conn.execute(
                "SELECT entrada_manual, salida_manual, motivo FROM jornadas_override WHERE jornada_id=?",
                (jornada_id,),
            ).fetchone()
        
        assert override[0] == "08:30:00"
        assert override[1] == "17:00:00"
        assert override[2] == "Prueba"

    def test_aplicar_override_salida_before_entrada_lanza_error(self, sample_override_data):
        """Salida antes de entrada → ValueError."""
        with get_conn_ctx() as conn:
            jornada_id = conn.execute(
                "SELECT id FROM jornadas WHERE empleado_id=1 AND fecha=?",
                ("2025-12-01",),
            ).fetchone()[0]
            
            with pytest.raises(ValueError, match="Salida <= Entrada"):
                aplicar_override(conn, jornada_id, "17:00", "08:00", "Invalid")

    def test_aplicar_override_jornada_inexistente(self, sample_override_data):
        """Override en jornada inexistente → RuntimeError."""
        with get_conn_ctx() as conn:
            with pytest.raises(RuntimeError, match="no encontrada"):
                aplicar_override(conn, 9999, "08:00", "17:30", "Error")

    def test_aplicar_override_multiples_veces(self, sample_override_data):
        """Aplicar override múltiples veces → se guarda histórico cada vez."""
        with get_conn_ctx() as conn:
            jornada_id = conn.execute(
                "SELECT id FROM jornadas WHERE empleado_id=1 AND fecha=?",
                ("2025-12-01",),
            ).fetchone()[0]
            
            aplicar_override(conn, jornada_id, "08:00", "17:30", "Override 1")
            aplicar_override(conn, jornada_id, "08:15", "17:45", "Override 2")
            aplicar_override(conn, jornada_id, "09:00", "18:00", "Override 3")
        
        with get_conn_ctx() as conn:
            overrides = conn.execute(
                "SELECT COUNT(*) FROM jornadas_override WHERE jornada_id=?",
                (jornada_id,),
            ).fetchone()[0]
            
            # último override debe estar en jornadas
            jornada = conn.execute(
                "SELECT entrada_calc, salida_calc FROM jornadas WHERE id=?",
                (jornada_id,),
            ).fetchone()
        
        assert overrides == 3  # historial de 3 overrides
        assert jornada[0] == "09:00:00"  # el último
        assert jornada[1] == "18:00:00"

    def test_aplicar_override_cambia_estado_ok(self, sample_override_data):
        """Aplicar override siempre pone estado OK."""
        with get_conn_ctx() as conn:
            jornada_id = conn.execute(
                "SELECT id FROM jornadas WHERE empleado_id=1 AND fecha=?",
                ("2025-12-01",),
            ).fetchone()[0]
            
            # jornada estaba en REVISAR
            aplicar_override(conn, jornada_id, "08:00", "17:30", "Fix")
        
        with get_conn_ctx() as conn:
            estado = conn.execute(
                "SELECT estado FROM jornadas WHERE id=?",
                (jornada_id,),
            ).fetchone()[0]
        
        assert estado == "OK"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
