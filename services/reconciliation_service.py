"""
Reconciliation Service

Provides daily reconciliation checking for position data integrity:
- Detects accounts with non-flat positions at end of trading day
- Identifies orphan trades (trades from missing source CSV files)
- Creates integrity issues for user review and resolution
"""

import logging
import sqlite3
import json
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from config import config
from domain.integrity_issue import IssueType, IssueSeverity

logger = logging.getLogger('reconciliation')


@dataclass
class ReconciliationIssue:
    """Represents a reconciliation issue for an account"""
    account: str
    issue_type: str
    running_quantity: int
    trade_count: int
    date_range: str
    description: str
    trade_ids: List[int]


class ReconciliationService:
    """
    Service for daily position reconciliation and orphan trade detection.

    Implements end-of-day checks to ensure:
    1. All positions are flat (running quantity = 0)
    2. All trades have valid source files
    """

    def __init__(self, db_path: str = None, data_dir: Path = None):
        """
        Initialize reconciliation service.

        Args:
            db_path: Path to database (default: config.db_path)
            data_dir: Data directory for CSV files (default: config.data_dir)
        """
        self.db_path = db_path or config.db_path
        self.data_dir = data_dir or config.data_dir
        self.logger = logging.getLogger('reconciliation')

    def check_account_positions(self, account: str = None) -> List[Dict[str, Any]]:
        """
        Check running quantity for accounts to detect non-flat positions.

        Args:
            account: Optional specific account to check (default: all accounts)

        Returns:
            List of accounts with non-zero running quantity
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Build query to calculate running quantity per account
            # Uses signed quantity based on side_of_market
            query = """
                WITH trade_quantities AS (
                    SELECT
                        account,
                        id as trade_id,
                        side_of_market,
                        quantity,
                        entry_time,
                        CASE
                            WHEN side_of_market IN ('Buy', 'BuyToCover') THEN quantity
                            WHEN side_of_market IN ('Sell', 'SellShort') THEN -quantity
                            ELSE 0
                        END as signed_quantity
                    FROM trades
                    WHERE deleted = 0
                    {account_filter}
                ),
                account_totals AS (
                    SELECT
                        account,
                        SUM(signed_quantity) as running_quantity,
                        COUNT(*) as trade_count,
                        MIN(entry_time) as first_trade,
                        MAX(entry_time) as last_trade,
                        GROUP_CONCAT(trade_id) as trade_ids
                    FROM trade_quantities
                    GROUP BY account
                )
                SELECT * FROM account_totals
                WHERE running_quantity != 0
                ORDER BY account
            """

            account_filter = f"AND account = '{account}'" if account else ""
            query = query.format(account_filter=account_filter)

            cursor.execute(query)
            results = []

            for row in cursor.fetchall():
                results.append({
                    'account': row['account'],
                    'running_quantity': row['running_quantity'],
                    'trade_count': row['trade_count'],
                    'date_range': f"{row['first_trade']} to {row['last_trade']}",
                    'trade_ids': [int(x) for x in row['trade_ids'].split(',')] if row['trade_ids'] else []
                })

            return results

        finally:
            conn.close()

    def get_account_trade_sequence(
        self,
        account: str,
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict[str, Any]]:
        """
        Get trade sequence with running quantity for an account.

        Args:
            account: Account to analyze
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of trades with running quantity at each step
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            query = """
                SELECT
                    id,
                    instrument,
                    side_of_market,
                    quantity,
                    entry_price,
                    exit_price,
                    entry_time,
                    entry_execution_id,
                    source_file
                FROM trades
                WHERE deleted = 0 AND account = ?
                {date_filter}
                ORDER BY entry_time, id
            """

            params = [account]
            date_filter = ""
            if start_date:
                date_filter += " AND entry_time >= ?"
                params.append(start_date)
            if end_date:
                date_filter += " AND entry_time <= ?"
                params.append(end_date)

            query = query.format(date_filter=date_filter)
            cursor.execute(query, params)

            trades = []
            running_qty = 0

            for row in cursor.fetchall():
                # Calculate signed change
                if row['side_of_market'] in ('Buy', 'BuyToCover'):
                    signed_change = row['quantity']
                else:
                    signed_change = -row['quantity']

                running_qty += signed_change

                trades.append({
                    'id': row['id'],
                    'instrument': row['instrument'],
                    'side_of_market': row['side_of_market'],
                    'quantity': row['quantity'],
                    'signed_change': signed_change,
                    'running_quantity': running_qty,
                    'entry_price': row['entry_price'],
                    'exit_price': row['exit_price'],
                    'entry_time': row['entry_time'],
                    'entry_execution_id': row['entry_execution_id'],
                    'source_file': row['source_file']
                })

            return trades

        finally:
            conn.close()

    def detect_orphan_trades(self, account: str = None) -> List[Dict[str, Any]]:
        """
        Detect trades whose source CSV files are missing.

        Args:
            account: Optional specific account to check

        Returns:
            List of orphan trade info grouped by missing source file
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Get all unique source files from trades
            query = """
                SELECT DISTINCT source_file
                FROM trades
                WHERE deleted = 0
                  AND source_file IS NOT NULL
                  AND source_file != ''
                {account_filter}
            """

            account_filter = f"AND account = '{account}'" if account else ""
            query = query.format(account_filter=account_filter)
            cursor.execute(query)

            source_files = [row['source_file'] for row in cursor.fetchall()]

            # Check which files exist
            missing_files = []
            for filename in source_files:
                file_path = self.data_dir / filename
                archive_path = self.data_dir / 'archive' / filename

                if not file_path.exists() and not archive_path.exists():
                    missing_files.append(filename)

            if not missing_files:
                return []

            # Get trades from missing files
            orphans = []
            for filename in missing_files:
                query = """
                    SELECT
                        COUNT(*) as trade_count,
                        GROUP_CONCAT(DISTINCT account) as accounts,
                        MIN(entry_time) as first_trade,
                        MAX(entry_time) as last_trade,
                        GROUP_CONCAT(id) as trade_ids
                    FROM trades
                    WHERE deleted = 0 AND source_file = ?
                    {account_filter}
                """
                query = query.format(account_filter=account_filter)
                cursor.execute(query, (filename,))
                row = cursor.fetchone()

                if row and row['trade_count'] > 0:
                    orphans.append({
                        'source_file': filename,
                        'trade_count': row['trade_count'],
                        'accounts': row['accounts'].split(',') if row['accounts'] else [],
                        'date_range': f"{row['first_trade']} to {row['last_trade']}",
                        'trade_ids': [int(x) for x in row['trade_ids'].split(',')] if row['trade_ids'] else []
                    })

            return orphans

        finally:
            conn.close()

    def get_trades_without_source(self, account: str = None) -> List[Dict[str, Any]]:
        """
        Get trades that have no source_file recorded (legacy imports).

        Args:
            account: Optional specific account to check

        Returns:
            List of trades without source file tracking
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            query = """
                SELECT
                    id, account, instrument, side_of_market, quantity,
                    entry_price, exit_price, entry_time, entry_execution_id
                FROM trades
                WHERE deleted = 0
                  AND (source_file IS NULL OR source_file = '')
                {account_filter}
                ORDER BY entry_time
            """

            account_filter = f"AND account = '{account}'" if account else ""
            query = query.format(account_filter=account_filter)
            cursor.execute(query)

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def run_daily_reconciliation(self) -> Dict[str, Any]:
        """
        Run full daily reconciliation check.

        This is intended to run at end of trading day to:
        1. Check all accounts for non-flat positions
        2. Detect orphan trades from missing CSV files

        Returns:
            Dictionary with reconciliation results
        """
        self.logger.info("Starting daily reconciliation check")

        # Check for non-flat accounts
        non_flat_accounts = self.check_account_positions()

        # Detect orphan trades
        orphan_trades = self.detect_orphan_trades()

        # Get trades without source tracking
        untracked_trades = self.get_trades_without_source()

        results = {
            'timestamp': datetime.now().isoformat(),
            'non_flat_accounts': non_flat_accounts,
            'orphan_trades': orphan_trades,
            'untracked_trade_count': len(untracked_trades),
            'has_issues': len(non_flat_accounts) > 0 or len(orphan_trades) > 0
        }

        # Log summary
        if non_flat_accounts:
            self.logger.warning(
                f"Found {len(non_flat_accounts)} accounts with non-flat positions"
            )
            for acct in non_flat_accounts:
                self.logger.warning(
                    f"  {acct['account']}: running={acct['running_quantity']}, "
                    f"trades={acct['trade_count']}"
                )

        if orphan_trades:
            self.logger.warning(
                f"Found {len(orphan_trades)} missing source files with orphan trades"
            )
            for orphan in orphan_trades:
                self.logger.warning(
                    f"  {orphan['source_file']}: {orphan['trade_count']} trades"
                )

        if not results['has_issues']:
            self.logger.info("Daily reconciliation passed - no issues found")

        return results

    def get_reconciliation_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current reconciliation status.

        Returns:
            Dictionary with current status summary
        """
        non_flat = self.check_account_positions()
        orphans = self.detect_orphan_trades()

        total_orphan_trades = sum(o['trade_count'] for o in orphans)

        return {
            'non_flat_account_count': len(non_flat),
            'non_flat_accounts': [a['account'] for a in non_flat],
            'orphan_file_count': len(orphans),
            'orphan_trade_count': total_orphan_trades,
            'has_issues': len(non_flat) > 0 or len(orphans) > 0
        }


# Create singleton instance for use by other modules
_reconciliation_service = None


def get_reconciliation_service() -> ReconciliationService:
    """Get singleton reconciliation service instance"""
    global _reconciliation_service
    if _reconciliation_service is None:
        _reconciliation_service = ReconciliationService()
    return _reconciliation_service
