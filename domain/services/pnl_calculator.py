"""
P&L Calculator - Pure domain service for calculating position P&L

Extracted from position_service.py to isolate P&L calculation logic
"""

from typing import List, Dict, Optional
from datetime import datetime
import logging
import json
import os

from ..models.position import Position, PositionType
from ..models.trade import Trade, MarketSide
from ..models.pnl import PnLCalculation, FIFOCalculator

logger = logging.getLogger('pnl_calculator')


class PnLCalculator:
    """
    Pure domain service for calculating position P&L using FIFO methodology
    """

    def __init__(self, instrument_config_path: Optional[str] = None):
        self.instrument_config_path = instrument_config_path or 'data/config/instrument_multipliers.json'
        self.fifo_calculator = FIFOCalculator()

    def calculate_position_pnl(self, position: Position, executions: List[Trade]) -> PnLCalculation:
        """
        Calculate position P&L from executions using FIFO methodology

        Separates entry and exit executions based on position direction:
        - Long position: Buy actions = entries, Sell actions = exits
        - Short position: Sell actions = entries, Buy actions = exits
        """
        if not executions:
            return PnLCalculation()

        # Separate entry and exit executions based on position direction
        entries = []
        exits = []

        for execution in executions:
            if position.position_type == PositionType.LONG:
                # Long position: Buy actions are entries, Sell actions are exits
                if execution.side_of_market in [MarketSide.BUY, MarketSide.BUY_TO_COVER, MarketSide.LONG]:
                    entries.append(self._trade_to_dict(execution))
                elif execution.side_of_market in [MarketSide.SELL, MarketSide.SELL_SHORT, MarketSide.SHORT]:
                    exits.append(self._trade_to_dict(execution))
            else:  # Short position
                # Short position: Sell actions are entries, Buy actions are exits
                if execution.side_of_market in [MarketSide.SELL, MarketSide.SELL_SHORT, MarketSide.SHORT]:
                    entries.append(self._trade_to_dict(execution))
                elif execution.side_of_market in [MarketSide.BUY, MarketSide.BUY_TO_COVER, MarketSide.LONG]:
                    exits.append(self._trade_to_dict(execution))

        # Get instrument multiplier
        multiplier = self._get_instrument_multiplier(position.instrument)

        # Calculate P&L using FIFO
        pnl_result = self.fifo_calculator.calculate_pnl(
            entries=entries,
            exits=exits,
            position_type=position.position_type.value,
            multiplier=multiplier
        )

        # Set position ID
        pnl_result.position_id = position.id

        return pnl_result

    def calculate_fifo_pnl(self, entries: List[Dict], exits: List[Dict], position_type: str) -> Dict:
        """
        Calculate P&L using FIFO (First In, First Out) methodology

        Matches entries with exits in chronological order to calculate precise P&L.
        This accounts for different entry/exit prices and quantities accurately.
        """
        if not entries or not exits:
            return {'points_pnl': 0, 'matched_quantity': 0}

        # Sort by entry_time for chronological matching
        sorted_entries = sorted(entries, key=lambda x: x.get('entry_time', ''))
        sorted_exits = sorted(exits, key=lambda x: x.get('entry_time', ''))

        total_pnl = 0
        matched_quantity = 0

        # FIFO matching algorithm
        entry_idx = 0
        exit_idx = 0
        remaining_entry_qty = 0
        remaining_exit_qty = 0

        while entry_idx < len(sorted_entries) and exit_idx < len(sorted_exits):
            entry = sorted_entries[entry_idx]
            exit = sorted_exits[exit_idx]

            # Get remaining quantities
            if remaining_entry_qty == 0:
                remaining_entry_qty = int(entry.get('quantity', 0))
            if remaining_exit_qty == 0:
                remaining_exit_qty = int(exit.get('quantity', 0))

            # Match the smaller quantity
            match_qty = min(remaining_entry_qty, remaining_exit_qty)

            if match_qty > 0:
                entry_price = float(entry.get('entry_price') or 0)
                exit_price = float(exit.get('exit_price') or exit.get('entry_price') or 0)

                # Calculate P&L for this match based on position type
                if position_type.lower() == 'long':
                    pnl_per_unit = exit_price - entry_price
                else:  # Short
                    pnl_per_unit = entry_price - exit_price

                match_pnl = pnl_per_unit * match_qty
                total_pnl += match_pnl
                matched_quantity += match_qty

                # Update remaining quantities
                remaining_entry_qty -= match_qty
                remaining_exit_qty -= match_qty

                # Move to next entry/exit if current one is fully matched
                if remaining_entry_qty == 0:
                    entry_idx += 1
                if remaining_exit_qty == 0:
                    exit_idx += 1

        return {
            'points_pnl': total_pnl,
            'matched_quantity': matched_quantity
        }

    def _trade_to_dict(self, trade: Trade) -> Dict:
        """
        Convert Trade object to dictionary for FIFO calculation

        Handles the case where CSV import stores prices in wrong fields:
        - For short position entries (Sell), price is incorrectly stored in exit_price
        - This method uses exit_price as fallback when entry_price is None
        """
        # Get entry_price, using exit_price as fallback if entry_price is None
        # This handles the bug where short position entries store price in exit_price field
        entry_price_value = trade.entry_price
        if entry_price_value is None and trade.exit_price is not None:
            # Fallback: Use exit_price if entry_price is None
            entry_price_value = trade.exit_price
            logger.debug(f"Trade {trade.id}: Using exit_price {trade.exit_price} as entry_price fallback")

        return {
            'quantity': trade.quantity,
            'entry_price': entry_price_value,
            'exit_price': trade.exit_price,
            'entry_time': trade.entry_time.isoformat() if trade.entry_time else '',
            'commission': trade.commission,
        }

    def _get_instrument_multiplier(self, instrument: str) -> float:
        """Get instrument multiplier for P&L calculations"""
        try:
            # First try the configured path
            config_path = self.instrument_config_path
            if not os.path.exists(config_path):
                # Fallback to working directory
                config_path = 'data/config/instrument_multipliers.json'

            with open(config_path, 'r') as f:
                multipliers = json.load(f)
            return float(multipliers.get(instrument, 1.0))
        except Exception as e:
            logger.warning(f"Could not load multiplier for {instrument}: {e}")
            return 1.0


class InstrumentMultiplierService:
    """Service for managing instrument multipliers"""

    def __init__(self, config_path: str = 'data/config/instrument_multipliers.json'):
        self.config_path = config_path
        self._multipliers = {}
        self._load_multipliers()

    def _load_multipliers(self):
        """Load multipliers from configuration file"""
        try:
            with open(self.config_path, 'r') as f:
                self._multipliers = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load instrument multipliers: {e}")
            self._multipliers = {}

    def get_multiplier(self, instrument: str) -> float:
        """Get multiplier for instrument"""
        return float(self._multipliers.get(instrument, 1.0))

    def set_multiplier(self, instrument: str, multiplier: float):
        """Set multiplier for instrument"""
        self._multipliers[instrument] = multiplier
        self._save_multipliers()

    def _save_multipliers(self):
        """Save multipliers to configuration file"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self._multipliers, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save instrument multipliers: {e}")

    def get_all_multipliers(self) -> Dict[str, float]:
        """Get all multipliers"""
        return self._multipliers.copy()

    def update_multipliers(self, multipliers: Dict[str, float]):
        """Update multiple multipliers"""
        self._multipliers.update(multipliers)
        self._save_multipliers()
