"""
Instrument Mapper Service

Maps NinjaTrader instrument names to Yahoo Finance symbols for OHLC data fetching.
Uses configuration from data/config/instrument_multipliers.json
"""

import json
import logging
from typing import List, Dict, Optional

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
