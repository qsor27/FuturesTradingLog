"""
Unit tests for InstrumentMapper

Tests the mapping of NinjaTrader instrument names to Yahoo Finance symbols.
"""

import pytest
import json
import tempfile
import os
from services.instrument_mapper import InstrumentMapper


class TestInstrumentMapper:
    """Test suite for InstrumentMapper class"""

    @pytest.fixture
    def sample_mappings(self):
        """Sample instrument mappings for testing"""
        return {
            "MNQ": {
                "name": "Micro E-mini NASDAQ-100",
                "yahoo_symbol": "NQ=F",
                "multiplier": 2,
                "tick_size": 0.25
            },
            "MES": {
                "name": "Micro E-mini S&P 500",
                "yahoo_symbol": "ES=F",
                "multiplier": 5,
                "tick_size": 0.25
            },
            "MGC": {
                "name": "Micro Gold",
                "yahoo_symbol": "GC=F",
                "multiplier": 10,
                "tick_size": 0.10
            }
        }

    @pytest.fixture
    def temp_config_file(self, sample_mappings):
        """Create temporary config file for testing"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_mappings, f)
            temp_path = f.name

        yield temp_path

        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    def test_extract_base_symbol_with_space(self, temp_config_file):
        """Test extracting base symbol from format with space"""
        mapper = InstrumentMapper(temp_config_file)

        assert mapper._extract_base_symbol("MNQ 12-24") == "MNQ"
        assert mapper._extract_base_symbol("MES 03-25") == "MES"
        assert mapper._extract_base_symbol("MGC 02-25") == "MGC"

    def test_extract_base_symbol_without_space(self, temp_config_file):
        """Test extracting base symbol from format without space"""
        mapper = InstrumentMapper(temp_config_file)

        assert mapper._extract_base_symbol("MNQ") == "MNQ"
        assert mapper._extract_base_symbol("MES") == "MES"
        assert mapper._extract_base_symbol("MGC") == "MGC"

    def test_extract_base_symbol_with_month_year(self, temp_config_file):
        """Test extracting base symbol from month/year format"""
        mapper = InstrumentMapper(temp_config_file)

        assert mapper._extract_base_symbol("MNQ MAR25") == "MNQ"
        assert mapper._extract_base_symbol("MES DEC24") == "MES"

    def test_extract_base_symbol_empty(self, temp_config_file):
        """Test extracting base symbol from empty string"""
        mapper = InstrumentMapper(temp_config_file)

        assert mapper._extract_base_symbol("") == ""
        assert mapper._extract_base_symbol(None) == ""

    def test_lookup_yahoo_symbol_found(self, temp_config_file):
        """Test looking up Yahoo symbol for known instrument"""
        mapper = InstrumentMapper(temp_config_file)

        assert mapper._lookup_yahoo_symbol("MNQ") == "NQ=F"
        assert mapper._lookup_yahoo_symbol("MES") == "ES=F"
        assert mapper._lookup_yahoo_symbol("MGC") == "GC=F"

    def test_lookup_yahoo_symbol_not_found(self, temp_config_file):
        """Test looking up Yahoo symbol for unknown instrument"""
        mapper = InstrumentMapper(temp_config_file)

        assert mapper._lookup_yahoo_symbol("UNKNOWN") is None
        assert mapper._lookup_yahoo_symbol("XYZ") is None

    def test_lookup_yahoo_symbol_empty(self, temp_config_file):
        """Test looking up Yahoo symbol for empty string"""
        mapper = InstrumentMapper(temp_config_file)

        assert mapper._lookup_yahoo_symbol("") is None
        assert mapper._lookup_yahoo_symbol(None) is None

    def test_map_to_yahoo_single_instrument(self, temp_config_file):
        """Test mapping single NinjaTrader instrument"""
        mapper = InstrumentMapper(temp_config_file)

        result = mapper.map_to_yahoo(["MNQ 12-24"])

        assert len(result) == 1
        assert "NQ=F" in result

    def test_map_to_yahoo_multiple_instruments(self, temp_config_file):
        """Test mapping multiple NinjaTrader instruments"""
        mapper = InstrumentMapper(temp_config_file)

        result = mapper.map_to_yahoo(["MNQ 12-24", "MES 03-25", "MGC 02-25"])

        assert len(result) == 3
        assert "NQ=F" in result
        assert "ES=F" in result
        assert "GC=F" in result

    def test_map_to_yahoo_with_duplicates(self, temp_config_file):
        """Test mapping removes duplicate Yahoo symbols"""
        mapper = InstrumentMapper(temp_config_file)

        # MNQ appears twice with different expirations
        result = mapper.map_to_yahoo(["MNQ 12-24", "MNQ 03-25", "MES 12-24"])

        # Should deduplicate NQ=F
        assert len(result) == 2
        assert "NQ=F" in result
        assert "ES=F" in result

    def test_map_to_yahoo_with_unknown_instruments(self, temp_config_file):
        """Test mapping with some unknown instruments"""
        mapper = InstrumentMapper(temp_config_file)

        result = mapper.map_to_yahoo(["MNQ 12-24", "UNKNOWN 12-24", "MES 03-25"])

        # Should skip unknown instrument
        assert len(result) == 2
        assert "NQ=F" in result
        assert "ES=F" in result

    def test_map_to_yahoo_empty_list(self, temp_config_file):
        """Test mapping empty instrument list"""
        mapper = InstrumentMapper(temp_config_file)

        result = mapper.map_to_yahoo([])

        assert len(result) == 0
        assert result == []

    def test_map_to_yahoo_all_unknown(self, temp_config_file):
        """Test mapping all unknown instruments"""
        mapper = InstrumentMapper(temp_config_file)

        result = mapper.map_to_yahoo(["UNKNOWN1", "UNKNOWN2", "UNKNOWN3"])

        assert len(result) == 0
        assert result == []

    def test_load_mappings_file_not_found(self):
        """Test loading mappings with non-existent file"""
        mapper = InstrumentMapper("nonexistent_file.json")

        # Should return empty dict without crashing
        assert mapper.mappings == {}

    def test_load_mappings_invalid_json(self):
        """Test loading mappings with invalid JSON"""
        # Create temp file with invalid JSON
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            mapper = InstrumentMapper(temp_path)

            # Should return empty dict without crashing
            assert mapper.mappings == {}
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_reload_mappings(self, temp_config_file):
        """Test reloading mappings from file"""
        mapper = InstrumentMapper(temp_config_file)

        # Initial load
        assert len(mapper.mappings) == 3

        # Modify config file
        new_mappings = {
            "MNQ": {
                "name": "Micro NASDAQ",
                "yahoo_symbol": "NQ=F",
                "multiplier": 2
            }
        }

        with open(temp_config_file, 'w') as f:
            json.dump(new_mappings, f)

        # Reload
        success = mapper.reload_mappings()

        assert success is True
        assert len(mapper.mappings) == 1

    def test_get_all_mappings(self, temp_config_file):
        """Test getting all mappings"""
        mapper = InstrumentMapper(temp_config_file)

        all_mappings = mapper.get_all_mappings()

        assert len(all_mappings) == 3
        assert "MNQ" in all_mappings
        assert "MES" in all_mappings
        assert "MGC" in all_mappings

    def test_get_mapping_found(self, temp_config_file):
        """Test getting specific mapping"""
        mapper = InstrumentMapper(temp_config_file)

        mapping = mapper.get_mapping("MNQ")

        assert mapping is not None
        assert mapping["yahoo_symbol"] == "NQ=F"
        assert mapping["multiplier"] == 2

    def test_get_mapping_not_found(self, temp_config_file):
        """Test getting mapping for unknown instrument"""
        mapper = InstrumentMapper(temp_config_file)

        mapping = mapper.get_mapping("UNKNOWN")

        assert mapping is None
