#!/bin/bash

echo "🚀 Starting FuturesTradingLog locally with Docker..."

# Stop any existing containers
docker stop futurestradinglog-dev 2>/dev/null || true
docker rm futurestradinglog-dev 2>/dev/null || true

# Run the container with proper environment setup
docker run -d \
  --name futurestradinglog-dev \
  -p 5000:5000 \
  -e FLASK_ENV=development \
  -e FLASK_DEBUG=1 \
  -e DATA_DIR=/app/data \
  -e FLASK_HOST=0.0.0.0 \
  -e FLASK_PORT=5000 \
  -e PYTHONPATH=/app \
  futurestradinglog-test

echo "✅ Container started!"
echo "📍 Application: http://localhost:5000"
echo "🔍 Health check: http://localhost:5000/health"
echo ""
echo "📋 To check logs: docker logs futurestradinglog-dev"
echo "⏹️  To stop: docker stop futurestradinglog-dev"