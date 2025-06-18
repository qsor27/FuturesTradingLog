import os
from flask import Blueprint, request, render_template
from TradingLog_db import FuturesDB

upload_bp = Blueprint('upload', __name__)

@upload_bp.route('/upload', methods=['GET'])
def upload_form():
    return render_template('upload.html')

@upload_bp.route('/upload', methods=['POST'])
def upload_file():
    # Debug: Check database structure
    with FuturesDB() as db:
        db.cursor.execute("SELECT * FROM sqlite_master WHERE type='table' AND name='trades'")
        table_info = db.cursor.fetchone()
        if table_info:
            print(f"Table structure:\n{table_info['sql']}")
        else:
            print("Table 'trades' not found!")
            
    if 'file' not in request.files:
        return 'No file uploaded', 400
    
    file = request.files['file']
    if file.filename == '':
        return 'No file selected', 400
    
    if file and file.filename.endswith('.csv'):
        temp_path = 'temp_trades.csv'
        file.save(temp_path)
        
        with FuturesDB() as db:
            success = db.import_csv(temp_path)
        
        os.remove(temp_path)
        
        if success:
            return 'File successfully imported', 200
        else:
            return 'Error importing file', 500
    
    return 'Invalid file type', 400
