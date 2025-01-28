from flask import Blueprint, render_template
from futures_db import FuturesDB

stats_bp = Blueprint('statistics', __name__)

@stats_bp.route('/statistics')
def statistics():
    with FuturesDB() as db:
        stats = {
            'daily': db.get_statistics('daily'),
            'weekly': db.get_statistics('weekly'),
            'monthly': db.get_statistics('monthly')
        }
    return render_template('statistics.html', stats=stats)