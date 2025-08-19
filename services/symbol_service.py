"""
Centralized Symbol Mapping Service for Futures Trading Log
Handles all instrument symbol transformations across the application
"""

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