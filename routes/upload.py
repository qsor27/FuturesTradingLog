import os
from flask import Blueprint, request, render_template
from scripts.TradingLog_db import FuturesDB

upload_bp = Blueprint('upload', __name__)

@upload_bp.route('/upload', methods=['GET'])
def upload_form():
    """DEPRECATED: Legacy upload form. Use /unified-csv-manager instead."""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("DEPRECATED: /upload form called. Use /unified-csv-manager with unified import system instead.")
    return render_template('upload.html')

# Route removed - using main.upload_file instead to avoid conflicts
