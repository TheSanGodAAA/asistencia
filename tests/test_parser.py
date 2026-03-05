"""Tests para core/parser.py"""

import pytest
from datetime import datetime
from core.parser import parse_line, parse_file, _map_estado
import tempfile
from pathlib import Path


class TestMapEstado:
    """Test de normalización de estado."""

    def test_m_ent(self):
        assert _map_estado("M/Ent") == "ENT"

    def test_m_sal(self):
        assert _map_estado("M/Sal") == "SAL"

    def test_ent_hrs_ext(self):
        assert _map_estado("Ent Hrs Ext") == "ENT"

    def test_sal_hrs_ext(self):
        assert _map_estado("Sal Hrs Ext") == "SAL"

    def test_unknown_estado(self):
        assert _map_estado("UNKNOWN") is None

    def test_whitespace_normalization(self):
        assert _map_estado("  m/ent  ") == "ENT"


class TestParseLine:
    """Test del parser de líneas individuales."""

    def test_valid_entrada(self):
        line = "      3   1/11/2025 7:59       M/Ent"
        result = parse_line(line)
        assert result is not None
        assert result["ac_no"] == 3
        assert result["tipo"] == "ENT"
        assert result["ts"] == "2025-11-01T07:59:00"

    def test_valid_salida(self):
        line = "      3  4/11/2025 11:55 Sal Hrs Ext"
        result = parse_line(line)
        assert result is not None
        assert result["ac_no"] == 3
        assert result["tipo"] == "SAL"

    def test_valid_entrada_with_seconds(self):
        line = "      3   1/11/2025 7:59:58       M/Ent"
        result = parse_line(line)
        assert result is not None
        assert result["ac_no"] == 3
        assert result["tipo"] == "ENT"
        assert result["ts"] == "2025-11-01T07:59:58"

    def test_header_line_ignored(self):
        line = "AC-NO       Fecha      Hora  Estado"
        result = parse_line(line)
        assert result is None

    def test_empty_line_ignored(self):
        line = ""
        result = parse_line(line)
        assert result is None

    def test_whitespace_line_ignored(self):
        line = "   \t   "
        result = parse_line(line)
        assert result is None

    def test_unknown_estado_ignored(self):
        line = "      5   1/11/2025 10:00  UNKNOWN_ESTADO"
        result = parse_line(line)
        assert result is None

    def test_malformed_line_ignored(self):
        line = "this is not a valid line at all"
        result = parse_line(line)
        assert result is None


class TestParseFile:
    """Test del parser de archivos."""

    def test_parse_file_multiple_lines(self):
        content = """      3   1/11/2025 7:59       M/Ent
      3  4/11/2025 11:55 Sal Hrs Ext
      5   2/11/2025 8:00 M/Ent
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="latin-1") as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            records = list(parse_file(temp_path))
            assert len(records) == 3
            assert records[0]["ac_no"] == 3
            assert records[1]["ac_no"] == 3
            assert records[2]["ac_no"] == 5
        finally:
            Path(temp_path).unlink()

    def test_parse_file_mixed_valid_invalid(self):
        content = """      3   1/11/2025 7:59       M/Ent
HEADER: this is invalid
      5   2/11/2025 8:00 M/Ent

      10  3/11/2025 9:00 M/Sal
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="latin-1") as f:
            f.write(content)
            f.flush()
            temp_path = f.name

        try:
            records = list(parse_file(temp_path))
            # solo 3 líneas válidas
            assert len(records) == 3
            assert records[0]["ac_no"] == 3
            assert records[1]["ac_no"] == 5
            assert records[2]["ac_no"] == 10
        finally:
            Path(temp_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
