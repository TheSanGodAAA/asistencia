"""Tests para core/importer.py"""

import pytest
from pathlib import Path
import tempfile
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.database import get_conn_ctx
from core.importer import import_txt, get_or_create_empleado, file_hash
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


class TestFileHash:
    """Test del hash de archivo."""

    def test_file_hash_consistency(self):
        """Hash del mismo archivo debe ser consistente."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("línea de prueba\n")
            f.flush()
            temp_path = Path(f.name)
        
        try:
            hash1 = file_hash(temp_path)
            hash2 = file_hash(temp_path)
            assert hash1 == hash2
        finally:
            temp_path.unlink()

    def test_file_hash_different_content(self):
        """Archivos diferentes deben tener hashes diferentes."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f1:
            f1.write("contenido 1\n")
            f1.flush()
            path1 = Path(f1.name)
        
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f2:
            f2.write("contenido 2\n")
            f2.flush()
            path2 = Path(f2.name)
        
        try:
            hash1 = file_hash(path1)
            hash2 = file_hash(path2)
            assert hash1 != hash2
        finally:
            path1.unlink()
            path2.unlink()


class TestGetOrCreateEmpleado:
    """Test de creación/obtención de empleados."""

    def test_get_existing_empleado(self, temp_db):
        """Obtener empleado existente."""
        with get_conn_ctx() as conn:
            conn.execute("INSERT INTO empleados (ac_no, nombre) VALUES (?, ?)", (123, "Juan"))
            
            emp_id = get_or_create_empleado(conn, 123)
            row = conn.execute("SELECT id, ac_no, nombre FROM empleados WHERE id=?", (emp_id,)).fetchone()
        
        assert row[1] == 123
        assert row[2] == "Juan"

    def test_create_new_empleado(self, temp_db):
        """Crear empleado si no existe."""
        with get_conn_ctx() as conn:
            emp_id = get_or_create_empleado(conn, 999)
            row = conn.execute("SELECT ac_no, nombre FROM empleados WHERE id=?", (emp_id,)).fetchone()
        
        assert row[0] == 999
        assert "999" in row[1]  # nombre contendrá el ac_no

    def test_get_or_create_idempotent(self, temp_db):
        """Múltiples llamadas deben devolver el mismo ID."""
        with get_conn_ctx() as conn:
            id1 = get_or_create_empleado(conn, 555)
            id2 = get_or_create_empleado(conn, 555)
            id3 = get_or_create_empleado(conn, 555)
        
        assert id1 == id2 == id3


class TestImportTxt:
    """Test de importación de archivo TXT."""

    def test_import_valid_records(self, temp_db):
        """Importar registros válidos."""
        records = [
            {"ac_no": 1, "ts": "2025-12-01T08:00:00", "tipo": "ENT", "raw": "line1"},
            {"ac_no": 1, "ts": "2025-12-01T17:30:00", "tipo": "SAL", "raw": "line2"},
            {"ac_no": 2, "ts": "2025-12-02T08:00:00", "tipo": "ENT", "raw": "line3"},
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("dummy")
            f.flush()
            temp_path = Path(f.name)
        
        try:
            import_txt(temp_path, records)
            
            with get_conn_ctx() as conn:
                marcaciones = conn.execute("SELECT COUNT(*) FROM marcaciones").fetchone()[0]
                empleados = conn.execute("SELECT COUNT(*) FROM empleados").fetchone()[0]
                imports = conn.execute("SELECT COUNT(*) FROM imports").fetchone()[0]
            
            assert marcaciones == 3
            assert empleados == 2
            assert imports == 1
        finally:
            temp_path.unlink()

    def test_import_duplicate_file(self, temp_db):
        """Importar el mismo archivo dos veces → segunda se omite."""
        records = [
            {"ac_no": 1, "ts": "2025-12-01T08:00:00", "tipo": "ENT"},
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("contenido fijo para test")
            f.flush()
            temp_path = Path(f.name)
        
        try:
            import_txt(temp_path, records)
            import_txt(temp_path, records)
            
            with get_conn_ctx() as conn:
                marcaciones = conn.execute("SELECT COUNT(*) FROM marcaciones").fetchone()[0]
                imports = conn.execute("SELECT COUNT(*) FROM imports").fetchone()[0]
            
            # solo la primera importación cuenta
            assert marcaciones == 1
            assert imports == 1
        finally:
            temp_path.unlink()

    def test_import_empty_records(self, temp_db):
        """Importar lista vacía de registros."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("vacio")
            f.flush()
            temp_path = Path(f.name)
        
        try:
            import_txt(temp_path, [])
            
            with get_conn_ctx() as conn:
                marcaciones = conn.execute("SELECT COUNT(*) FROM marcaciones").fetchone()[0]
                imports = conn.execute("SELECT COUNT(*) FROM imports").fetchone()[0]
            
            assert marcaciones == 0
            assert imports == 1  # el import se registra igual
        finally:
            temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
