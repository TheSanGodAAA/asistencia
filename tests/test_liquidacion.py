"""Tests para core/liquidacion.py"""

import pytest
from pathlib import Path
import tempfile
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import date
from db.database import get_conn_ctx
from core.liquidacion import crear_borrador_liquidacion, cerrar_liquidacion, _tarifa_cent, _monto_cent
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
def sample_liquidacion_data(temp_db):
    """Crear empleados, tarifas y jornadas para liquidación."""
    with get_conn_ctx() as conn:
        # empleados
        conn.execute("INSERT INTO empleados (ac_no, nombre) VALUES (1, 'Juan')")
        conn.execute("INSERT INTO empleados (ac_no, nombre) VALUES (2, 'Maria')")
        
        emp1_id = conn.execute("SELECT id FROM empleados WHERE ac_no=1").fetchone()[0]
        emp2_id = conn.execute("SELECT id FROM empleados WHERE ac_no=2").fetchone()[0]
        
        # tarifas (UYU/hora)
        # Juan: 100 UYU/hora = 10000 centavos
        conn.execute(
            """
            INSERT INTO tarifas_empleado (empleado_id, desde, pago_hora_cent, nota)
            VALUES (?, ?, ?, ?)
            """,
            (emp1_id, "2025-12-01", 10000, "Tarifa Juan"),
        )
        # Maria: 150 UYU/hora = 15000 centavos
        conn.execute(
            """
            INSERT INTO tarifas_empleado (empleado_id, desde, pago_hora_cent, nota)
            VALUES (?, ?, ?, ?)
            """,
            (emp2_id, "2025-12-01", 15000, "Tarifa Maria"),
        )
        
        # jornadas (minutos calculados)
        # Juan: 480 min (8h) en OK
        conn.execute(
            """
            INSERT INTO jornadas (empleado_id, fecha, minutos_calc, estado)
            VALUES (?, ?, ?, ?)
            """,
            (emp1_id, "2025-12-01", 480, "OK"),
        )
        # Juan: 360 min (6h) en OK
        conn.execute(
            """
            INSERT INTO jornadas (empleado_id, fecha, minutos_calc, estado)
            VALUES (?, ?, ?, ?)
            """,
            (emp1_id, "2025-12-02", 360, "OK"),
        )
        # Maria: 600 min (10h) en OK
        conn.execute(
            """
            INSERT INTO jornadas (empleado_id, fecha, minutos_calc, estado)
            VALUES (?, ?, ?, ?)
            """,
            (emp2_id, "2025-12-01", 600, "OK"),
        )
    
    return temp_db


class TestTarifaCent:
    """Test de obtención de tarifa en centavos."""

    def test_tarifa_cent_exists(self, sample_liquidacion_data):
        """Obtener tarifa vigente de un empleado."""
        with get_conn_ctx() as conn:
            emp_id = conn.execute("SELECT id FROM empleados WHERE ac_no=1").fetchone()[0]
            tarifa = _tarifa_cent(conn, emp_id, date(2025, 12, 1))
        
        assert tarifa == 10000  # 100 UYU = 10000 centavos

    def test_tarifa_cent_missing(self, sample_liquidacion_data):
        """Tarifa no existe → lanza RuntimeError."""
        with get_conn_ctx() as conn:
            emp_id = conn.execute("SELECT id FROM empleados WHERE ac_no=1").fetchone()[0]
        
        with pytest.raises(RuntimeError, match="sin tarifa vigente"):
            with get_conn_ctx() as conn:
                _tarifa_cent(conn, emp_id, date(2024, 12, 1))  # fecha anterior sin tarifa


class TestMontoCent:
    """Test de cálculo de monto en centavos."""

    def test_monto_cent_calculation(self):
        """Calcular monto: minutos * (cent/hora) / 60."""
        # 480 min * 10000 cent/60 min = 80000 cent = 800 UYU
        monto = _monto_cent(480, 10000)
        assert monto == 80000

    def test_monto_cent_rounding(self):
        """Redondeo a centésimo."""
        # 100 min * 15000 cent / 60 = 25000 cent = 250 UYU
        monto = _monto_cent(100, 15000)
        assert monto == 25000

    def test_monto_cent_partial_hour(self):
        """Monto para fracción de hora."""
        # 30 min * 10000 cent / 60 = 5000 cent = 50 UYU
        monto = _monto_cent(30, 10000)
        assert monto == 5000


class TestCrearBorradorLiquidacion:
    """Test de creación de liquidación borrador."""

    def test_crear_borrador_simple(self, sample_liquidacion_data):
        """Crear borrador de liquidación."""
        lid = crear_borrador_liquidacion(2025, 12)
        
        assert lid is not None
        
        with get_conn_ctx() as conn:
            # verificar liquidacion
            liq = conn.execute(
                "SELECT anio, mes, estado FROM liquidaciones WHERE id=?", (lid,)
            ).fetchone()
            assert liq == (2025, 12, "BORRADOR")
            
            # verificar detalle (2 empleados)
            detalle = conn.execute(
                "SELECT COUNT(*) FROM liquidacion_detalle WHERE liquidacion_id=?", (lid,)
            ).fetchone()[0]
            assert detalle == 2
            
            # verificar cálculo Juan: (480 + 360) * 10000 / 60 = 140000 cent
            juan = conn.execute(
                """
                SELECT minutos_pagados, monto_cent FROM liquidacion_detalle
                WHERE liquidacion_id=? AND empleado_id=?
                """,
                (lid, 1),
            ).fetchone()
            assert juan[0] == 840  # 480 + 360
            assert juan[1] == 140000

    def test_crear_borrador_twice_recalcula(self, sample_liquidacion_data):
        """Crear borrador dos veces → la segunda recalcula."""
        lid1 = crear_borrador_liquidacion(2025, 12)
        
        # añadir una jornada más
        with get_conn_ctx() as conn:
            conn.execute(
                """
                INSERT INTO jornadas (empleado_id, fecha, minutos_calc, estado)
                VALUES (?, ?, ?, ?)
                """,
                (1, "2025-12-03", 240, "OK"),
            )
        
        lid2 = crear_borrador_liquidacion(2025, 12)
        
        assert lid1 == lid2  # mismo ID
        
        with get_conn_ctx() as conn:
            juan = conn.execute(
                """
                SELECT minutos_pagados FROM liquidacion_detalle
                WHERE liquidacion_id=? AND empleado_id=?
                """,
                (lid2, 1),
            ).fetchone()
            # 480 + 360 + 240 = 1080
            assert juan[0] == 1080

    def test_crear_borrador_cerrado_lanza_error(self, sample_liquidacion_data):
        """No se puede recalcular liquidación cerrada."""
        lid = crear_borrador_liquidacion(2025, 12)
        cerrar_liquidacion(2025, 12)
        
        with pytest.raises(RuntimeError, match="CERRADA"):
            crear_borrador_liquidacion(2025, 12)

    def test_crear_borrador_empleado_sin_tarifa(self, temp_db):
        """Empleado sin tarifa → lanza error."""
        with get_conn_ctx() as conn:
            conn.execute("INSERT INTO empleados (ac_no, nombre) VALUES (99, 'SinTarifa')")
            emp_id = conn.execute("SELECT id FROM empleados WHERE ac_no=99").fetchone()[0]
            
            # jornada sin tarifa asociada
            conn.execute(
                """
                INSERT INTO jornadas (empleado_id, fecha, minutos_calc, estado)
                VALUES (?, ?, ?, ?)
                """,
                (emp_id, "2025-12-01", 480, "OK"),
            )
        
        with pytest.raises(RuntimeError, match="sin tarifa vigente"):
            crear_borrador_liquidacion(2025, 12)

    def test_vale_descuenta_neto(self, sample_liquidacion_data):
        """Un vale del mes descuenta el neto de liquidación."""
        with get_conn_ctx() as conn:
            conn.execute(
                """
                INSERT INTO vales (empleado_id, fecha, monto_cent, nota, creado_en)
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                (1, "2025-12-15", 40000, "Vale prueba"),
            )

        lid = crear_borrador_liquidacion(2025, 12)

        with get_conn_ctx() as conn:
            row = conn.execute(
                """
                SELECT monto_cent, vales_cent, monto_final_cent
                FROM liquidacion_detalle
                WHERE liquidacion_id=? AND empleado_id=?
                """,
                (lid, 1),
            ).fetchone()

        # bruto Juan = 140000 cent; vale = 40000; neto = 100000
        assert row[0] == 140000
        assert row[1] == 40000
        assert row[2] == 100000

    def test_arrastre_vale_mes_siguiente(self, temp_db):
        """Si vales superan el bruto, el monto final puede ser negativo y se crea vale del mes siguiente."""
        with get_conn_ctx() as conn:
            conn.execute("INSERT INTO empleados (ac_no, nombre) VALUES (10, 'Emp Arrastre')")
            emp_id = conn.execute("SELECT id FROM empleados WHERE ac_no=10").fetchone()[0]
            conn.execute(
                """
                INSERT INTO tarifas_empleado (empleado_id, desde, pago_hora_cent, nota)
                VALUES (?, ?, ?, ?)
                """,
                (emp_id, "2025-12-01", 10000, "Tarifa"),
            )

            # Enero: bruto 10000 cent (1h), vale 20000 => neto -10000 y nuevo vale 10000 para febrero
            conn.execute(
                "INSERT INTO jornadas (empleado_id, fecha, minutos_calc, estado) VALUES (?, ?, ?, ?)",
                (emp_id, "2026-01-10", 60, "OK"),
            )
            conn.execute(
                """
                INSERT INTO vales (empleado_id, fecha, monto_cent, nota, creado_en)
                VALUES (?, ?, ?, ?, datetime('now'))
                """,
                (emp_id, "2026-01-12", 20000, "Vale enero"),
            )

        lid_ene = crear_borrador_liquidacion(2026, 1)

        with get_conn_ctx() as conn:
            ene = conn.execute(
                """
                SELECT monto_cent, vales_cent, monto_final_cent
                FROM liquidacion_detalle WHERE liquidacion_id=? AND empleado_id=?
                """,
                (lid_ene, emp_id),
            ).fetchone()
            vale_arrastre = conn.execute(
                """
                SELECT fecha, monto_cent, es_arrastre, origen_anio, origen_mes
                FROM vales
                WHERE empleado_id=? AND es_arrastre=1 AND origen_anio=2026 AND origen_mes=1
                """,
                (emp_id,),
            ).fetchone()

        assert ene == (10000, 20000, -10000)
        assert vale_arrastre == ("2026-02-01", 10000, 1, 2026, 1)

        with get_conn_ctx() as conn:
            # Febrero: bruto 30000 cent (3h), y entra el vale de arrastre de 10000 => neto 20000
            conn.execute(
                "INSERT INTO jornadas (empleado_id, fecha, minutos_calc, estado) VALUES (?, ?, ?, ?)",
                (emp_id, "2026-02-10", 180, "OK"),
            )

        lid_feb = crear_borrador_liquidacion(2026, 2)

        with get_conn_ctx() as conn:
            feb = conn.execute(
                """
                SELECT monto_cent, vales_cent, monto_final_cent
                FROM liquidacion_detalle WHERE liquidacion_id=? AND empleado_id=?
                """,
                (lid_feb, emp_id),
            ).fetchone()

        assert feb == (30000, 10000, 20000)


class TestCerrarLiquidacion:
    """Test de cierre de liquidación."""

    def test_cerrar_borrador(self, sample_liquidacion_data):
        """Cerrar una liquidación borrador."""
        lid = crear_borrador_liquidacion(2025, 12)
        cerrar_liquidacion(2025, 12)
        
        with get_conn_ctx() as conn:
            liq = conn.execute(
                "SELECT estado, cerrado_en FROM liquidaciones WHERE id=?", (lid,)
            ).fetchone()
        
        assert liq[0] == "CERRADO"
        assert liq[1] is not None  # timestamp de cierre

    def test_cerrar_dos_veces_idempotente(self, sample_liquidacion_data):
        """Cerrar dos veces → la segunda es idempotente."""
        crear_borrador_liquidacion(2025, 12)
        cerrar_liquidacion(2025, 12)
        cerrar_liquidacion(2025, 12)  # no lanza error
        
        with get_conn_ctx() as conn:
            liq = conn.execute(
                "SELECT estado FROM liquidaciones WHERE anio=2025 AND mes=12"
            ).fetchone()
        
        assert liq[0] == "CERRADO"

    def test_cerrar_inexistente(self, sample_liquidacion_data):
        """Cerrar liquidación que no existe → lanza error."""
        with pytest.raises(RuntimeError, match="No existe liquidación"):
            cerrar_liquidacion(2025, 11)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
