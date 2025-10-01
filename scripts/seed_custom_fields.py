"""
Database Seeder for Default Custom Fields

Seeds the database with commonly used custom field definitions for trading positions.
This provides a good starting point for users before they create their own custom fields.
"""

import sqlite3
import sys
import os
from pathlib import Path
import json
import logging
from typing import List, Dict, Any

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from config.config import AppConfig
except ImportError:
    # Fallback if config import fails
    class AppConfig:
        def __init__(self):
            self.db_dir = Path(__file__).parent.parent / 'data' / 'db'
            self.db_path = self.db_dir / 'futures_trades_clean.db'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Default custom field definitions
DEFAULT_CUSTOM_FIELDS = [
    {
        'name': 'trade_reviewed',
        'label': 'Trade Reviewed',
        'field_type': 'boolean',
        'description': 'Mark if this trade has been reviewed',
        'is_required': False,
        'default_value': 'false',
        'sort_order': 1,
        'validation_rules': json.dumps({'required': False}),
        'is_active': True,
        'created_by': 1
    },
    {
        'name': 'setup_type',
        'label': 'Setup Type',
        'field_type': 'select',
        'description': 'Type of trading setup used',
        'is_required': False,
        'default_value': '',
        'sort_order': 2,
        'validation_rules': json.dumps({
            'options': ['breakout', 'pullback', 'reversal', 'continuation', 'scalp', 'swing']
        }),
        'is_active': True,
        'created_by': 1
    },
    {
        'name': 'market_sentiment',
        'label': 'Market Sentiment',
        'field_type': 'select',
        'description': 'Overall market sentiment at time of trade',
        'is_required': False,
        'default_value': 'neutral',
        'sort_order': 3,
        'validation_rules': json.dumps({
            'options': ['bullish', 'bearish', 'neutral', 'uncertain']
        }),
        'is_active': True,
        'created_by': 1
    },
    {
        'name': 'trade_confidence',
        'label': 'Trade Confidence (1-10)',
        'field_type': 'number',
        'description': 'Confidence level in this trade setup (1-10)',
        'is_required': False,
        'default_value': '5',
        'sort_order': 4,
        'validation_rules': json.dumps({
            'min': 1,
            'max': 10,
            'integer': True
        }),
        'is_active': True,
        'created_by': 1
    },
    {
        'name': 'risk_reward_ratio',
        'label': 'Risk/Reward Ratio',
        'field_type': 'number',
        'description': 'Expected risk to reward ratio',
        'is_required': False,
        'default_value': '',
        'sort_order': 5,
        'validation_rules': json.dumps({
            'min': 0,
            'decimal': True
        }),
        'is_active': True,
        'created_by': 1
    },
    {
        'name': 'market_session',
        'label': 'Market Session',
        'field_type': 'select',
        'description': 'Trading session when position was opened',
        'is_required': False,
        'default_value': '',
        'sort_order': 6,
        'validation_rules': json.dumps({
            'options': ['pre_market', 'open', 'morning', 'lunch', 'afternoon', 'close', 'after_hours']
        }),
        'is_active': True,
        'created_by': 1
    },
    {
        'name': 'news_impact',
        'label': 'News Impact',
        'field_type': 'select',
        'description': 'Expected impact of news events',
        'is_required': False,
        'default_value': 'neutral',
        'sort_order': 7,
        'validation_rules': json.dumps({
            'options': ['high_positive', 'moderate_positive', 'low_positive', 'neutral',
                       'low_negative', 'moderate_negative', 'high_negative']
        }),
        'is_active': True,
        'created_by': 1
    },
    {
        'name': 'extended_notes',
        'label': 'Extended Notes',
        'field_type': 'text',
        'description': 'Additional detailed notes about this position',
        'is_required': False,
        'default_value': '',
        'sort_order': 8,
        'validation_rules': json.dumps({
            'maxLength': 2000
        }),
        'is_active': True,
        'created_by': 1
    }
]


# Options for select fields (must match field names above)
FIELD_OPTIONS = {
    'setup_type': [
        ('breakout', 'Breakout', 1),
        ('pullback', 'Pullback', 2),
        ('reversal', 'Reversal', 3),
        ('continuation', 'Continuation', 4),
        ('scalp', 'Scalp', 5),
        ('swing', 'Swing', 6)
    ],
    'market_sentiment': [
        ('bullish', 'Bullish', 1),
        ('bearish', 'Bearish', 2),
        ('neutral', 'Neutral', 3),
        ('uncertain', 'Uncertain', 4)
    ],
    'market_session': [
        ('pre_market', 'Pre-Market', 1),
        ('open', 'Market Open', 2),
        ('morning', 'Morning Session', 3),
        ('lunch', 'Lunch Time', 4),
        ('afternoon', 'Afternoon Session', 5),
        ('close', 'Market Close', 6),
        ('after_hours', 'After Hours', 7)
    ],
    'news_impact': [
        ('high_positive', 'High Positive', 1),
        ('moderate_positive', 'Moderate Positive', 2),
        ('low_positive', 'Low Positive', 3),
        ('neutral', 'Neutral', 4),
        ('low_negative', 'Low Negative', 5),
        ('moderate_negative', 'Moderate Negative', 6),
        ('high_negative', 'High Negative', 7)
    ]
}


def get_db_connection(db_path: str = None) -> sqlite3.Connection:
    """Get database connection"""
    if db_path is None:
        config = AppConfig()
        db_path = str(config.db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def field_exists(conn: sqlite3.Connection, field_name: str) -> bool:
    """Check if a custom field already exists"""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM custom_fields WHERE name = ?", (field_name,))
    count = cursor.fetchone()[0]
    return count > 0


def create_custom_field(conn: sqlite3.Connection, field_data: Dict[str, Any]) -> int:
    """Create a custom field and return its ID"""
    cursor = conn.cursor()

    query = """
        INSERT INTO custom_fields
        (name, label, field_type, description, is_required, default_value,
         sort_order, validation_rules, is_active, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    params = (
        field_data['name'],
        field_data['label'],
        field_data['field_type'],
        field_data['description'],
        field_data['is_required'],
        field_data['default_value'],
        field_data['sort_order'],
        field_data['validation_rules'],
        field_data['is_active'],
        field_data['created_by']
    )

    cursor.execute(query, params)
    return cursor.lastrowid


def create_field_options(conn: sqlite3.Connection, field_id: int, field_name: str) -> None:
    """Create options for a select field"""
    if field_name not in FIELD_OPTIONS:
        return

    cursor = conn.cursor()

    query = """
        INSERT INTO custom_field_options
        (custom_field_id, option_value, option_label, sort_order)
        VALUES (?, ?, ?, ?)
    """

    for option_value, option_label, sort_order in FIELD_OPTIONS[field_name]:
        cursor.execute(query, (field_id, option_value, option_label, sort_order))


def seed_default_custom_fields(db_path: str = None, skip_existing: bool = True) -> bool:
    """Seed database with default custom fields"""
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()

        # Check if custom_fields table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='custom_fields'
        """)

        if not cursor.fetchone():
            logger.error("custom_fields table does not exist. Run migration first.")
            return False

        created_count = 0
        skipped_count = 0

        logger.info(f"Starting to seed {len(DEFAULT_CUSTOM_FIELDS)} default custom fields...")

        for field_data in DEFAULT_CUSTOM_FIELDS:
            field_name = field_data['name']

            # Check if field already exists
            if skip_existing and field_exists(conn, field_name):
                logger.info(f"Skipping existing field: {field_name}")
                skipped_count += 1
                continue

            try:
                # Create the custom field
                field_id = create_custom_field(conn, field_data)

                # Create options if it's a select field
                if field_data['field_type'] == 'select':
                    create_field_options(conn, field_id, field_name)

                logger.info(f"Created custom field: {field_name} (ID: {field_id})")
                created_count += 1

            except sqlite3.IntegrityError as e:
                logger.warning(f"Failed to create field '{field_name}': {e}")
                conn.rollback()
                continue

        # Commit all changes
        conn.commit()

        logger.info(f"Seeding complete: {created_count} fields created, {skipped_count} skipped")
        return True

    except Exception as e:
        logger.error(f"Error during seeding: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False
    finally:
        if 'conn' in locals():
            conn.close()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Seed default custom fields')
    parser.add_argument('--db-path', type=str, help='Path to database file (optional)')
    parser.add_argument('--force', action='store_true',
                       help='Create fields even if they already exist (may cause errors)')

    args = parser.parse_args()

    # Run seeder
    success = seed_default_custom_fields(
        db_path=args.db_path,
        skip_existing=not args.force
    )

    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()