#!/bin/bash
echo "Installing dependencies..."
pip install -r requirements-minimal.txt

echo "Setting up data directories..."
mkdir -p /app/data/db /app/data/logs /app/data/config /app/data/charts /app/data/archive

echo "Cleaning up any corrupted database files..."
rm -f /app/data/db/*.db-shm /app/data/db/*.db-wal

echo "Setting permissions..."
chmod -R 755 /app/data

echo "Starting Flask application in development mode..."
export FLASK_ENV=development
export FLASK_DEBUG=1
export DATA_DIR=/app/data
export PYTHONPATH=/app

python -u app.py