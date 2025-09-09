#!/bin/bash

# Fix permissions on the data directory
echo "Fixing data directory permissions..."
chown -R appuser:appuser /app/data 2>/dev/null || true

# Switch to appuser and run the application
echo "Starting application as appuser..."
exec gosu appuser python app.py