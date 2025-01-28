from flask import Flask
from routes.trades import trades_bp
from routes.upload import upload_bp
from routes.statistics import stats_bp
from futures_db import FuturesDB

app = Flask(__name__)

# Register blueprints
app.register_blueprint(trades_bp)
app.register_blueprint(upload_bp)
app.register_blueprint(stats_bp)

# Add utility functions to template context
@app.context_processor
def utility_processor():
    return {
        'min': min,
        'max': max
    }

if __name__ == '__main__':
    with FuturesDB() as db:
        pass
    
    app.run(debug=True, port=5000)