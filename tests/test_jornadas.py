"""Tests para core/jornadas.py"""

import pytest
import sqlite3
from datetime import date, time, datetime, timedelta
from pathlib import Path
import tempfile
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import get_conn_ctx
from core.jornadas import calcular_jornadas, _get_horario, _clamp_entrada, _clamp_salida
from db.init_db import init_db


@pytest.fixture(scope="function")
def temp_db():
    """Crear una DB temporal para tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    # Parchear PATH temporalmente
    import db.database as db_mod
    original_db_path = db_mod.DB_PATH
    db_mod.DB_PATH = Path(db_path)
    
    # Inicializar schema
    init_db()
    
    yield Path(db_path)
    
    # Limpiar
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
def sample_data(temp_db):
    """Crear empleados, horarios y marcaciones de prueba."""
    with get_conn_ctx() as conn:
        # crear empleados
        conn.execute("INSERT INTO empleados (ac_no, nombre) VALUES (1, 'Juan')")
        conn.execute("INSERT INTO empleados (ac_no, nombre) VALUES (2, 'Maria')")
        
        # crear horario vigencia (08:00 - 17:30, tolerancia 5 min)
        conn.execute(
            """
            INSERT INTO horarios_vigencia (desde, hora_inicio, hora_fin, tolerancia_min, nota)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("2025-01-01", "08:00", "17:30", 5, "Horario estándar"),
        )
        
    return temp_db


class TestClampFunctions:
    """Test de funciones de ajuste de entrada/salida."""

    def test_clamp_entrada_before_horario(self, sample_data):
        """Entrada antes del horario → se clampea a hora inicio."""
        ts = datetime(2025, 12, 1, 7, 30, 0, 0)
        hi = time(8, 0)
        result = _clamp_entrada(ts, hi, tol_min=10)
        assert result.time() == time(8, 0)

    def test_clamp_entrada_within_tolerance(self, sample_data):
        """Entrada dentro de tolerancia → se clampea a hora inicio."""
        ts = datetime(2025, 12, 1, 8, 5, 0, 0)
        hi = time(8, 0)
        result = _clamp_entrada(ts, hi, tol_min=10)
        assert result.time() == time(8, 0)

    def test_clamp_entrada_after_tolerance(self, sample_data):
        """Entrada después de tolerancia → se mantiene."""
        ts = datetime(2025, 12, 1, 8, 15, 0, 0)
        hi = time(8, 0)
        result = _clamp_entrada(ts, hi, tol_min=10)
        assert result.time() == time(8, 15)

    def test_clamp_salida_after_horario(self, sample_data):
        """Salida después del horario → se clampea a hora fin."""
        ts = datetime(2025, 12, 1, 18, 0, 0, 0)
        hf = time(17, 30)
        result = _clamp_salida(ts, hf)
        assert result.time() == time(17, 30)

    def test_clamp_salida_within_tolerance_before(self, sample_data):
        """Salida dentro de tolerancia antes de fin → se clampea."""
        ts = datetime(2025, 12, 1, 17, 20, 0, 0)
        hf = time(17, 30)
        result = _clamp_salida(ts, hf, tol_salida_min=10)
        assert result.time() == time(17, 30)

    def test_clamp_salida_before_tolerance(self, sample_data):
        """Salida muy temprano → se mantiene."""
        ts = datetime(2025, 12, 1, 16, 0, 0, 0)
        hf = time(17, 30)
        result = _clamp_salida(ts, hf, tol_salida_min=10)
        assert result.time() == time(16, 0)


class TestCalcularJornadas:
    """Test de cálculo de jornadas."""

    def test_jornada_normal_ok(self, sample_data):
        """Jornada normal (1 entrada + 1 salida) → estado OK."""
        with get_conn_ctx() as conn:
            emp_id = conn.execute("SELECT id FROM empleados WHERE ac_no=1").fetchone()[0]
            
            # crear marcaciones
            conn.execute(
                "INSERT INTO marcaciones (empleado_id, ts, tipo) VALUES (?, ?, ?)",
                (emp_id, "2025-12-01T08:00:00", "ENT"),
            )
            conn.execute(
                "INSERT INTO marcaciones (empleado_id, ts, tipo) VALUES (?, ?, ?)",
                (emp_id, "2025-12-01T17:30:00", "SAL"),
            )
        
        # calcular
        calcular_jornadas(date(2025, 12, 1), date(2025, 12, 1))
        
        # verificar
        with get_conn_ctx() as conn:
            row = conn.execute(
                "SELECT estado, minutos_calc FROM jornadas WHERE empleado_id=? AND fecha=?",
                (emp_id, "2025-12-01"),
            ).fetchone()
        
        assert row is not None
        estado, minutos = row
        assert estado == "OK"
        assert minutos == 570  # 9.5 horas = 570 min

    def test_jornada_falta_salida(self, sample_data):
        """Jornada sin salida → estado REVISAR."""
        with get_conn_ctx() as conn:
            emp_id = conn.execute("SELECT id FROM empleados WHERE ac_no=2").fetchone()[0]
            
            conn.execute(
                "INSERT INTO marcaciones (empleado_id, ts, tipo) VALUES (?, ?, ?)",
                (emp_id, "2025-12-01T08:00:00", "ENT"),
            )
        
        calcular_jornadas(date(2025, 12, 1), date(2025, 12, 1))
        
        with get_conn_ctx() as conn:
            row = conn.execute(
                "SELECT estado, detalle FROM jornadas WHERE empleado_id=? AND fecha=?",
                (emp_id, "2025-12-01"),
            ).fetchone()
        
        assert row is not None
        estado, detalle = row
        assert estado == "REVISAR"
        assert "salida" in detalle.lower()

    def test_jornada_sin_marcaciones(self, sample_data):
        """Día sin marcaciones → no hay jornada calculada."""
        with get_conn_ctx() as conn:
            emp_id = conn.execute("SELECT id FROM empleados WHERE ac_no=1").fetchone()[0]
        
        calcular_jornadas(date(2025, 12, 1), date(2025, 12, 1))
        
        with get_conn_ctx() as conn:
            row = conn.execute(
                "SELECT id FROM jornadas WHERE empleado_id=? AND fecha=?",
                (emp_id, "2025-12-01"),
            ).fetchone()
        
        assert row is None

    def test_jornada_doble_entrada(self, sample_data):
        """Dos entradas + una salida → estado REVISAR."""
        with get_conn_ctx() as conn:
            emp_id = conn.execute("SELECT id FROM empleados WHERE ac_no=1").fetchone()[0]
            
            conn.execute(
                "INSERT INTO marcaciones (empleado_id, ts, tipo) VALUES (?, ?, ?)",
                (emp_id, "2025-12-01T08:00:00", "ENT"),
            )
            conn.execute(
                "INSERT INTO marcaciones (empleado_id, ts, tipo) VALUES (?, ?, ?)",
                (emp_id, "2025-12-01T09:00:00", "ENT"),
            )
            conn.execute(
                "INSERT INTO marcaciones (empleado_id, ts, tipo) VALUES (?, ?, ?)",
                (emp_id, "2025-12-01T17:30:00", "SAL"),
            )
        
        calcular_jornadas(date(2025, 12, 1), date(2025, 12, 1))
        
        with get_conn_ctx() as conn:
            row = conn.execute(
                "SELECT estado FROM jornadas WHERE empleado_id=? AND fecha=?",
                (emp_id, "2025-12-01"),
            ).fetchone()
        
        assert row[0] == "REVISAR"

    def test_jornada_partido_4_marcas(self, sample_data):
        """Jornada partida (ENT, SAL, ENT, SAL) → estado OK con minutos sumados."""
        with get_conn_ctx() as conn:
            emp_id = conn.execute("SELECT id FROM empleados WHERE ac_no=1").fetchone()[0]
            
            # Tramo 1: 08:00 - 12:15 (255 min)
            conn.execute(
                "INSERT INTO marcaciones (empleado_id, ts, tipo) VALUES (?, ?, ?)",
                (emp_id, "2025-12-01T08:00:00", "ENT"),
            )
            conn.execute(
                "INSERT INTO marcaciones (empleado_id, ts, tipo) VALUES (?, ?, ?)",
                (emp_id, "2025-12-01T12:15:00", "SAL"),
            )
            # Tramo 2: 13:00 - 17:30 (270 min)
            conn.execute(
                "INSERT INTO marcaciones (empleado_id, ts, tipo) VALUES (?, ?, ?)",
                (emp_id, "2025-12-01T13:00:00", "ENT"),
            )
            conn.execute(
                "INSERT INTO marcaciones (empleado_id, ts, tipo) VALUES (?, ?, ?)",
                (emp_id, "2025-12-01T17:30:00", "SAL"),
            )
        
        calcular_jornadas(date(2025, 12, 1), date(2025, 12, 1))
        
        with get_conn_ctx() as conn:
            row = conn.execute(
                "SELECT estado, minutos_calc FROM jornadas WHERE empleado_id=? AND fecha=?",
                (emp_id, "2025-12-01"),
            ).fetchone()
        
        assert row[0] == "OK"
        # 255 + 270 + 45 (descanso pago) = 570
        assert row[1] == 570


class TestGetHorario:
    """Test de obtención de horario vigente."""

    def test_get_horario_vigencia(self, sample_data):
        """Obtener horario vigente para una fecha."""
        with get_conn_ctx() as conn:
            hi, hf, tol = _get_horario(conn, date(2025, 12, 1))
        
        assert hi == time(8, 0)
        assert hf == time(17, 30)
        assert tol == 5

    def test_get_horario_no_vigencia(self, sample_data):
        """Sin horario vigencia configurado → lanza error."""
        with get_conn_ctx() as conn:
            conn.execute("DELETE FROM horarios_vigencia")
        
        with pytest.raises(RuntimeError, match="No hay horario vigente"):
            with get_conn_ctx() as conn:
                _get_horario(conn, date(2025, 12, 1))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
