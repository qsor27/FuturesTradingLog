"""
Centralized Symbol Mapping Service for Futures Trading Log
Handles all instrument symbol transformations across the application
"""
import re
import logging
from datetime import datetime, date
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Standard futures month codes
MONTH_NAME_TO_CODE = {
    'JAN': 'F', 'FEB': 'G', 'MAR': 'H', 'APR': 'J',
    'MAY': 'K', 'JUN': 'M', 'JUL': 'N', 'AUG': 'Q',
    'SEP': 'U', 'OCT': 'V', 'NOV': 'X', 'DEC': 'Z'
}

# Numeric month to code mapping (for "12-25" format)
MONTH_NUM_TO_CODE = {
    '01': 'F', '02': 'G', '03': 'H', '04': 'J',
    '05': 'K', '06': 'M', '07': 'N', '08': 'Q',
    '09': 'U', '10': 'V', '11': 'X', '12': 'Z',
    # Also support single digit months
    '1': 'F', '2': 'G', '3': 'H', '4': 'J',
    '5': 'K', '6': 'M', '7': 'N', '8': 'Q',
    '9': 'U'
}

# Reverse mapping: month code to month number
MONTH_CODE_TO_NUM = {
    'F': 1, 'G': 2, 'H': 3, 'J': 4,
    'K': 5, 'M': 6, 'N': 7, 'Q': 8,
    'U': 9, 'V': 10, 'X': 11, 'Z': 12
}

# Month name to number
MONTH_NAME_TO_NUM = {
    'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4,
    'MAY': 5, 'JUN': 6, 'JUL': 7, 'AUG': 8,
    'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
}


class SymbolMappingService:
    """Centralized service for all instrument symbol transformations"""
    
    def __init__(self):
        # Mapping from base symbols to yfinance symbols
        # Based on Yahoo Finance research - CORRECTED MAPPINGS
        self.yfinance_mapping = {
            # Nasdaq
            'MNQ': 'MNQ=F',    # Micro E-mini Nasdaq-100 (CORRECTED from NQ=F)
            'NQ': 'NQ=F',      # E-mini Nasdaq-100
            
            # S&P 500
            'MES': 'MES=F',    # Micro E-mini S&P 500 (CORRECTED from ES=F)
            'ES': 'ES=F',      # E-mini S&P 500
            
            # Russell 2000
            'M2K': 'RTY=F',    # Micro E-mini Russell 2000 (maps to RTY=F)
            'RTY': 'RTY=F',    # E-mini Russell 2000
            
            # Dow Jones
            'MYM': 'YM=F',     # Micro E-mini Dow (maps to YM=F) 
            'YM': 'YM=F',      # E-mini Dow Jones
            
            # Commodities
            'CL': 'CL=F',      # Crude Oil
            'GC': 'GC=F',      # Gold
            'SI': 'SI=F',      # Silver
            'ZN': 'ZN=F',      # 10-Year Treasury Note
            'ZB': 'ZB=F',      # 30-Year Treasury Bond
            'HG': 'HG=F',      # Copper
            'NG': 'NG=F',      # Natural Gas
            
            # Currencies
            '6E': '6E=F',      # Euro
            '6J': '6J=F',      # Japanese Yen
            '6B': '6B=F',      # British Pound
            '6A': '6A=F',      # Australian Dollar
        }
        
        # Human-readable display names
        self.display_names = {
            'MNQ': 'Micro NASDAQ-100',
            'NQ': 'NASDAQ-100', 
            'MES': 'Micro S&P 500',
            'ES': 'S&P 500',
            'RTY': 'Russell 2000',
            'M2K': 'Micro Russell 2000',
            'YM': 'Dow Jones',
            'MYM': 'Micro Dow Jones',
            'CL': 'Crude Oil',
            'GC': 'Gold',
            'SI': 'Silver',
            'ZN': '10-Year Treasury Note',
            'ZB': '30-Year Treasury Bond',
            'HG': 'Copper',
            'NG': 'Natural Gas',
            '6E': 'Euro',
            '6J': 'Japanese Yen',
            '6B': 'British Pound',
            '6A': 'Australian Dollar',
        }
        
        # Contract multipliers (points to dollars)
        self.multipliers = {
            'MNQ': 2,      # $2 per point
            'NQ': 20,      # $20 per point
            'MES': 5,      # $5 per point  
            'ES': 50,      # $50 per point
            'RTY': 50,     # $50 per point
            'M2K': 5,      # $5 per point
            'YM': 5,       # $5 per point
            'MYM': 0.5,    # $0.50 per point
            'CL': 1000,    # $1000 per point
            'GC': 100,     # $100 per point
            'SI': 5000,    # $5000 per point
        }
    
    def get_base_symbol(self, instrument: str) -> str:
        """
        Extract base symbol from any instrument format
        
        Examples:
        - "MNQ SEP25" -> "MNQ"
        - "MNQ" -> "MNQ"
        - "ES DEC24" -> "ES"
        """
        if not instrument:
            return ""
        return instrument.split()[0].upper()
    
    def get_yfinance_symbol(self, instrument: str) -> str:
        """
        Get yfinance symbol for any instrument format
        
        Examples:
        - "MNQ SEP25" -> "MNQ=F"
        - "MNQ" -> "MNQ=F"
        - "ES DEC24" -> "ES=F"
        """
        base = self.get_base_symbol(instrument)
        return self.yfinance_mapping.get(base, f"{base}=F")
    
    def get_display_name(self, instrument: str) -> str:
        """
        Get human-readable display name
        
        Examples:
        - "MNQ SEP25" -> "Micro NASDAQ-100"
        - "ES" -> "S&P 500"
        """
        base = self.get_base_symbol(instrument)
        return self.display_names.get(base, base)
    
    def get_full_display_name(self, instrument: str) -> str:
        """
        Get full display name including expiration if present
        
        Examples:
        - "MNQ SEP25" -> "Micro NASDAQ-100 SEP25"
        - "ES" -> "S&P 500"
        """
        parts = instrument.split()
        base_display = self.get_display_name(instrument)
        
        if len(parts) > 1:
            # Include expiration month
            return f"{base_display} {' '.join(parts[1:])}"
        else:
            return base_display
    
    def get_multiplier(self, instrument: str) -> float:
        """
        Get contract multiplier (points to dollars)
        
        Examples:
        - "MNQ SEP25" -> 2.0
        - "ES" -> 50.0
        """
        base = self.get_base_symbol(instrument)
        return self.multipliers.get(base, 1.0)
    
    def normalize_for_storage(self, instrument: str) -> str:
        """
        Normalize instrument symbol for database storage
        Always returns base symbol without expiration
        
        Examples:
        - "MNQ SEP25" -> "MNQ"
        - "MNQ" -> "MNQ"
        """
        return self.get_base_symbol(instrument)
    
    def validate_symbol(self, instrument: str) -> bool:
        """
        Check if symbol is supported
        
        Examples:
        - "MNQ SEP25" -> True
        - "INVALID" -> False
        """
        base = self.get_base_symbol(instrument)
        return base in self.yfinance_mapping
    
    def get_contract_type(self, instrument: str) -> str:
        """
        Determine if contract is micro, mini, or full size
        
        Examples:
        - "MNQ" -> "micro"
        - "NQ" -> "mini" 
        - "CL" -> "full"
        """
        base = self.get_base_symbol(instrument)
        
        if base.startswith('M') and len(base) == 3:
            # Micro contracts: MNQ, MES, M2K, MYM
            return "micro"
        elif base in ['NQ', 'ES', 'RTY', 'YM']:
            # E-mini contracts
            return "mini"
        else:
            # Full-size contracts
            return "full"
    
    def get_related_contracts(self, instrument: str) -> dict:
        """
        Get related contracts (micro/mini versions)
        
        Examples:
        - "MNQ" -> {"micro": "MNQ", "mini": "NQ"}
        - "ES" -> {"micro": "MES", "mini": "ES"}
        """
        base = self.get_base_symbol(instrument)
        
        # Define relationships
        relationships = {
            'MNQ': {'micro': 'MNQ', 'mini': 'NQ'},
            'NQ': {'micro': 'MNQ', 'mini': 'NQ'},
            'MES': {'micro': 'MES', 'mini': 'ES'},
            'ES': {'micro': 'MES', 'mini': 'ES'},
            'M2K': {'micro': 'M2K', 'mini': 'RTY'},
            'RTY': {'micro': 'M2K', 'mini': 'RTY'},
            'MYM': {'micro': 'MYM', 'mini': 'YM'},
            'YM': {'micro': 'MYM', 'mini': 'YM'},
        }
        
        return relationships.get(base, {'micro': None, 'mini': None, 'full': base})
    
    def is_micro_contract(self, instrument: str) -> bool:
        """Check if instrument is a micro contract"""
        return self.get_contract_type(instrument) == "micro"
    
    def is_supported(self, instrument: str) -> bool:
        """Alias for validate_symbol for better readability"""
        return self.validate_symbol(instrument)

    def parse_contract_expiration(self, instrument: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Parse NinjaTrader contract name into components.

        Supports formats:
        - "MNQ SEP25" -> ('MNQ', 'U', '25')
        - "MNQ 09-25" -> ('MNQ', 'U', '25')
        - "ES 12-24" -> ('ES', 'Z', '24')
        - "MNQ" -> ('MNQ', None, None)

        Returns:
            Tuple of (base_symbol, month_code, year) where month_code and year
            may be None if no expiration is present
        """
        if not instrument:
            return ("", None, None)

        parts = instrument.strip().upper().split()
        base_symbol = parts[0]

        if len(parts) < 2:
            # No expiration specified
            return (base_symbol, None, None)

        expiration = parts[1]

        # Try format: "SEP25" (month name + year)
        month_name_match = re.match(r'^([A-Z]{3})(\d{2})$', expiration)
        if month_name_match:
            month_name = month_name_match.group(1)
            year = month_name_match.group(2)
            month_code = MONTH_NAME_TO_CODE.get(month_name)
            if month_code:
                return (base_symbol, month_code, year)

        # Try format: "09-25" or "12-25" (numeric month-year)
        numeric_match = re.match(r'^(\d{1,2})-(\d{2})$', expiration)
        if numeric_match:
            month_num = numeric_match.group(1).zfill(2)  # Ensure 2 digits
            year = numeric_match.group(2)
            month_code = MONTH_NUM_TO_CODE.get(month_num)
            if month_code:
                return (base_symbol, month_code, year)

        # Could not parse expiration
        return (base_symbol, None, None)

    def get_yfinance_contract_symbol(self, instrument: str) -> str:
        """
        Convert NinjaTrader format to Yahoo Finance contract symbol.

        Examples:
        - "MNQ SEP25" -> "MNQU25.CME"
        - "ES 12-24" -> "ESZ24.CME"
        - "NQ MAR26" -> "NQH26.CME"
        - "MNQ" -> "MNQ=F" (fallback to continuous if no expiration)

        Returns:
            Yahoo Finance symbol for the specific contract month,
            or continuous contract symbol if no expiration specified
        """
        base_symbol, month_code, year = self.parse_contract_expiration(instrument)

        if month_code and year:
            # Individual contract: e.g., MNQU25.CME
            return f"{base_symbol}{month_code}{year}.CME"
        else:
            # No expiration specified, use continuous contract
            return self.get_yfinance_symbol(instrument)

    def has_expiration(self, instrument: str) -> bool:
        """
        Check if instrument includes an expiration date.

        Examples:
        - "MNQ SEP25" -> True
        - "MNQ" -> False
        """
        _, month_code, year = self.parse_contract_expiration(instrument)
        return month_code is not None and year is not None

    def normalize_for_ohlc_storage(self, instrument: str) -> str:
        """
        Normalize instrument for OHLC data storage.
        Returns full contract name if expiration is present,
        otherwise returns base symbol.

        This keeps OHLC data tied to specific contracts.

        Examples:
        - "MNQ SEP25" -> "MNQ SEP25"
        - "mnq sep25" -> "MNQ SEP25"
        - "MNQ" -> "MNQ"
        """
        if not instrument:
            return ""
        return instrument.strip().upper()

    def _get_third_friday(self, year: int, month: int) -> date:
        """
        Calculate the 3rd Friday of a given month (standard futures expiration).

        Args:
            year: Full year (e.g., 2025)
            month: Month number (1-12)

        Returns:
            date object for the 3rd Friday
        """
        # Find the first day of the month
        first_day = date(year, month, 1)

        # Find the first Friday (weekday 4 = Friday)
        days_until_friday = (4 - first_day.weekday()) % 7
        first_friday = first_day.day + days_until_friday

        # Third Friday is 14 days after first Friday
        third_friday = first_friday + 14

        return date(year, month, third_friday)

    def get_contract_expiration_date(self, instrument: str) -> Optional[date]:
        """
        Get the expiration date for a futures contract.

        Futures contracts typically expire on the 3rd Friday of the contract month.

        Args:
            instrument: Contract name (e.g., "MNQ SEP25", "ES DEC24")

        Returns:
            date object for expiration, or None if no expiration specified

        Examples:
        - "MNQ SEP25" -> date(2025, 9, 19)  # 3rd Friday of Sep 2025
        - "MNQ DEC25" -> date(2025, 12, 19) # 3rd Friday of Dec 2025
        - "MNQ" -> None
        """
        base_symbol, month_code, year_str = self.parse_contract_expiration(instrument)

        if not month_code or not year_str:
            return None

        # Convert month code to month number
        month = MONTH_CODE_TO_NUM.get(month_code)
        if not month:
            # Try month name directly from the instrument
            parts = instrument.strip().upper().split()
            if len(parts) >= 2:
                # Extract month name (first 3 chars of expiration)
                month_name = parts[1][:3]
                month = MONTH_NAME_TO_NUM.get(month_name)

        if not month:
            logger.warning(f"Could not determine month for contract: {instrument}")
            return None

        # Convert 2-digit year to full year
        year = int(year_str)
        if year < 100:
            # Assume 20xx for years 00-99
            year = 2000 + year

        return self._get_third_friday(year, month)

    def is_contract_expired(self, instrument: str, reference_date: Optional[date] = None) -> bool:
        """
        Check if a futures contract has expired.

        Args:
            instrument: Contract name (e.g., "MNQ SEP25")
            reference_date: Date to compare against (default: today)

        Returns:
            True if the contract has expired, False otherwise.
            Returns False for continuous contracts (no expiration specified).

        Examples:
        - "MNQ SEP25" on Dec 18, 2025 -> True (expired in Sept)
        - "MNQ DEC25" on Dec 18, 2025 -> False (expires Dec 19, 2025)
        - "MNQ MAR26" on Dec 18, 2025 -> False (future contract)
        - "MNQ" -> False (continuous contract, never expires)
        """
        if reference_date is None:
            reference_date = date.today()

        expiration = self.get_contract_expiration_date(instrument)

        if expiration is None:
            # No expiration = continuous contract, never expires
            return False

        return reference_date > expiration

    def filter_active_contracts(self, instruments: list, reference_date: Optional[date] = None) -> list:
        """
        Filter a list of instruments to only include active (non-expired) contracts.

        Args:
            instruments: List of instrument names
            reference_date: Date to compare against (default: today)

        Returns:
            List of instruments that have not expired
        """
        if reference_date is None:
            reference_date = date.today()

        active = []
        expired = []

        for instrument in instruments:
            if self.is_contract_expired(instrument, reference_date):
                expired.append(instrument)
            else:
                active.append(instrument)

        if expired:
            logger.info(f"Filtered out {len(expired)} expired contracts: {expired}")

        return active


# Global instance for use across the application
symbol_service = SymbolMappingService()


# Convenience functions for backward compatibility
def get_base_symbol(instrument: str) -> str:
    """Get base symbol - convenience function"""
    return symbol_service.get_base_symbol(instrument)

def get_yfinance_symbol(instrument: str) -> str:
    """Get yfinance symbol - convenience function"""
    return symbol_service.get_yfinance_symbol(instrument)

def normalize_instrument(instrument: str) -> str:
    """Normalize instrument for storage - convenience function"""
    return symbol_service.normalize_for_storage(instrument)

def get_yfinance_contract_symbol(instrument: str) -> str:
    """Get yfinance contract-specific symbol - convenience function"""
    return symbol_service.get_yfinance_contract_symbol(instrument)

def normalize_for_ohlc_storage(instrument: str) -> str:
    """Normalize instrument for OHLC storage - convenience function"""
    return symbol_service.normalize_for_ohlc_storage(instrument)

def parse_contract_expiration(instrument: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Parse contract expiration - convenience function"""
    return symbol_service.parse_contract_expiration(instrument)

def is_contract_expired(instrument: str) -> bool:
    """Check if contract has expired - convenience function"""
    return symbol_service.is_contract_expired(instrument)

def filter_active_contracts(instruments: list) -> list:
    """Filter to only active contracts - convenience function"""
    return symbol_service.filter_active_contracts(instruments)