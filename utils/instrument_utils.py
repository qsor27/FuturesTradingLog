"""
Instrument normalization utilities for futures trading log
"""
import re
from services.symbol_service import symbol_service

def get_root_symbol(instrument_name: str) -> str:
    """
    Extracts the root symbol from a futures contract name.
    This is crucial for querying data providers with a generic ticker.
    Example: 'MNQ SEP25' -> 'MNQ'
    """
    # Use the existing symbol service for consistency
    return symbol_service.get_base_symbol(instrument_name)

def normalize_instrument_for_ohlc(instrument_name: str) -> str:
    """
    Normalizes instrument name for OHLC data storage.
    Ensures consistent storage format across the application.
    """
    return get_root_symbol(instrument_name)