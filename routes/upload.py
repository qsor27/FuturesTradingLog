import os
from flask import Blueprint, request, render_template
from scripts.TradingLog_db import FuturesDB

upload_bp = Blueprint('upload', __name__)

@upload_bp.route('/upload', methods=['GET'])
def upload_form():
    return render_template('upload.html')

# Route removed - using main.upload_file instead to avoid conflicts
