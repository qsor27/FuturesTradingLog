"""
Instrument Mapper Service

Maps NinjaTrader instrument names to Yahoo Finance symbols for OHLC data fetching.
Handles contract-specific naming (MNQ MAR26) and continuous contracts (MNQ=F).
Uses configuration from data/config/instrument_multipliers.json
"""

import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class InstrumentMapper:
    """
    Maps NinjaTrader instrument names to Yahoo Finance symbols

    NinjaTrader format: "MNQ 12-24" (symbol + expiration)
    Yahoo Finance format: "NQ=F" (continuous futures contract)
    """

    def __init__(self, config_path: str = 'data/config/instrument_multipliers.json'):
        """
        Initialize mapper with config file path

        Args:
            config_path: Path to instrument mappings JSON file
        """
        self.config_path = config_path
        self.mappings = self._load_mappings()

    def _load_mappings(self) -> Dict[str, Dict]:
        """
        Load instrument mappings from JSON config

        Expected format:
        {
            "MNQ": {
                "name": "Micro E-mini NASDAQ-100",
                "yahoo_symbol": "NQ=F",
                "multiplier": 2,
                "tick_size": 0.25
            },
            ...
        }

        Returns:
            Dictionary of instrument mappings
        """
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Instrument mappings file not found: {self.config_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse instrument mappings JSON: {e}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load instrument mappings: {e}")
            return {}

    def _extract_base_symbol(self, nt_instrument: str) -> str:
        """
        Extract base symbol from NinjaTrader instrument name

        Examples:
        - "MNQ 12-24" -> "MNQ"
        - "MES 03-25" -> "MES"
        - "MGC" -> "MGC"
        - "NQ MAR25" -> "NQ"

        Args:
            nt_instrument: NinjaTrader instrument name

        Returns:
            Base symbol (part before space or entire string)
        """
        if not nt_instrument:
            return ""

        # Split on space and take first part
        parts = nt_instrument.strip().split()
        return parts[0] if parts else nt_instrument

    def _lookup_yahoo_symbol(self, base_symbol: str) -> Optional[str]:
        """
        Look up Yahoo Finance symbol for base symbol

        Args:
            base_symbol: Base symbol (e.g., "MNQ", "MES")

        Returns:
            Yahoo Finance symbol (e.g., "NQ=F") or None if not found
        """
        if not base_symbol:
            return None

        # Check if base symbol exists in mappings
        if base_symbol in self.mappings:
            mapping = self.mappings[base_symbol]

            # Handle both old format (just multiplier) and new format (dict with yahoo_symbol)
            if isinstance(mapping, dict):
                return mapping.get('yahoo_symbol')
            else:
                # Old format - just a multiplier number
                # Log warning that mapping needs to be updated
                logger.warning(f"Old format mapping found for {base_symbol}, please update config to include yahoo_symbol")
                return None

        return None

    def map_to_yahoo(self, ninjatrader_instruments: List[str]) -> List[str]:
        """
        Map NinjaTrader instrument names to Yahoo Finance symbols

        Args:
            ninjatrader_instruments: List of NinjaTrader format names
                Example: ['MNQ 12-24', 'MES 12-24', 'MGC 02-25']

        Returns:
            List of Yahoo Finance symbols (deduplicated)
                Example: ['NQ=F', 'ES=F', 'GC=F']

        Note:
            - Automatically deduplicates results
            - Logs warnings for unmapped instruments
            - Returns empty list if no valid mappings found
        """
        if not ninjatrader_instruments:
            logger.warning("Empty instrument list provided to mapper")
            return []

        yahoo_symbols = []

        for nt_instrument in ninjatrader_instruments:
            # Extract base symbol (e.g., "MNQ 12-24" -> "MNQ")
            base_symbol = self._extract_base_symbol(nt_instrument)

            if not base_symbol:
                logger.warning(f"Could not extract base symbol from '{nt_instrument}'")
                continue

            # Look up Yahoo Finance symbol
            yahoo_symbol = self._lookup_yahoo_symbol(base_symbol)

            if yahoo_symbol:
                yahoo_symbols.append(yahoo_symbol)
                logger.debug(f"Mapped '{nt_instrument}' -> '{yahoo_symbol}'")
            else:
                logger.warning(
                    f"No Yahoo Finance mapping for '{nt_instrument}' "
                    f"(base: '{base_symbol}'). Please update {self.config_path}"
                )

        # Remove duplicates while preserving order
        unique_symbols = list(dict.fromkeys(yahoo_symbols))

        logger.info(f"Mapped {len(ninjatrader_instruments)} instruments to {len(unique_symbols)} Yahoo Finance symbols")

        return unique_symbols

    def reload_mappings(self) -> bool:
        """
        Reload mappings from config file

        Useful for updating mappings without restarting application

        Returns:
            True if reload successful, False otherwise
        """
        try:
            self.mappings = self._load_mappings()
            logger.info(f"Reloaded instrument mappings from {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to reload instrument mappings: {e}")
            return False

    def get_all_mappings(self) -> Dict[str, Dict]:
        """
        Get all instrument mappings

        Returns:
            Dictionary of all mappings
        """
        return self.mappings.copy()

    def get_mapping(self, base_symbol: str) -> Optional[Dict]:
        """
        Get mapping for specific instrument

        Args:
            base_symbol: Base symbol to look up

        Returns:
            Mapping dictionary or None if not found
        """
        return self.mappings.get(base_symbol)

    def get_root_symbol(self, instrument: str) -> str:
        """
        Extract root symbol from contract-specific or any instrument name

        This is the continuous contract symbol without expiration date.

        Examples:
        - "MNQ MAR26" -> "MNQ"
        - "MES DEC25" -> "MES"
        - "ES 12-24" -> "ES"
        - "NQ" -> "NQ"

        Args:
            instrument: Any instrument format

        Returns:
            Root symbol (base symbol without contract month/year)
        """
        return self._extract_base_symbol(instrument)

    # Contract-specific methods

    MONTH_CODES = {
        'JAN': 'F', 'FEB': 'G', 'MAR': 'H', 'APR': 'J',
        'MAY': 'K', 'JUN': 'M', 'JUL': 'N', 'AUG': 'Q',
        'SEP': 'U', 'OCT': 'V', 'NOV': 'X', 'DEC': 'Z'
    }

    def parse_contract(self, instrument: str) -> Optional[Dict[str, str]]:
        """
        Parse contract-specific instrument name

        Formats supported:
        - "MNQ MAR26" -> base=MNQ, month=MAR, year=26
        - "MNQ DEC25" -> base=MNQ, month=DEC, year=25
        - "ES JUN26" -> base=ES, month=JUN, year=26

        Args:
            instrument: Contract instrument name

        Returns:
            Dict with 'base', 'month', 'year' or None if not a contract format
        """
        # Pattern: BASE MONTHYEAR (e.g., "MNQ MAR26" or "ES DEC25")
        pattern = r'^([A-Z]+)\s+([A-Z]{3})(\d{2})$'
        match = re.match(pattern, instrument.strip().upper())

        if match:
            base, month, year = match.groups()
            if month in self.MONTH_CODES:
                return {
                    'base': base,
                    'month': month,
                    'year': year,
                    'full_year': f"20{year}"
                }

        return None

    def normalize_to_contract(self, instrument: str, default_contract: Optional[str] = None) -> str:
        """
        Normalize instrument name to contract format

        Args:
            instrument: Any instrument format
            default_contract: Default contract to use if instrument is continuous (e.g., "MAR26")

        Returns:
            Normalized contract format: "BASE MONTHYY" (e.g., "MNQ MAR26")
        """
        # Already in contract format?
        if self.parse_contract(instrument):
            return instrument.upper()

        # Extract base symbol
        base = self._extract_base_symbol(instrument)

        # If default contract provided, use it
        if default_contract:
            return f"{base} {default_contract}".upper()

        # Infer current quarter contract
        now = datetime.now()
        year = now.strftime('%y')

        # Futures quarterly months: MAR, JUN, SEP, DEC
        month = now.month
        if month <= 3:
            contract_month = 'MAR'
        elif month <= 6:
            contract_month = 'JUN'
        elif month <= 9:
            contract_month = 'SEP'
        else:
            contract_month = 'DEC'

        return f"{base} {contract_month}{year}"

    def get_yahoo_for_contract(self, instrument: str) -> Tuple[str, str]:
        """
        Get Yahoo Finance symbol and storage instrument name for a contract

        Args:
            instrument: NinjaTrader instrument (e.g., "MNQ MAR26" or "MNQ 12-24")

        Returns:
            Tuple of (yahoo_symbol, storage_instrument)
            - yahoo_symbol: Symbol to use for fetching data (e.g., "NQ=F")
            - storage_instrument: Normalized name for storage (e.g., "MNQ MAR26")
        """
        # Parse if contract format
        parsed = self.parse_contract(instrument)
        if parsed:
            # It's a contract - use it for storage
            storage_instrument = f"{parsed['base']} {parsed['month']}{parsed['year']}"
            # Get Yahoo symbol for the base
            yahoo_symbol = self._lookup_yahoo_symbol(parsed['base'])
            return (yahoo_symbol or f"{parsed['base']}=F", storage_instrument)

        # Not contract format - extract base and normalize
        base = self._extract_base_symbol(instrument)
        yahoo_symbol = self._lookup_yahoo_symbol(base)

        # Try to extract contract from old format "MNQ 12-24"
        pattern = r'(\d{2})-(\d{2})'
        match = re.search(pattern, instrument)
        if match:
            month_num, year = match.groups()
            # Convert month number to name (12->DEC, 03->MAR, etc.)
            month_names = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                          'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
            month_idx = int(month_num) - 1
            if 0 <= month_idx < 12:
                month_name = month_names[month_idx]
                storage_instrument = f"{base} {month_name}{year}"
                return (yahoo_symbol or f"{base}=F", storage_instrument)

        # Fallback: infer current contract
        storage_instrument = self.normalize_to_contract(instrument)
        return (yahoo_symbol or f"{base}=F", storage_instrument)
