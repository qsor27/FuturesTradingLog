# Multi-stage build for optimized production image
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=/app/app.py \
    PYTHONPATH=/app \
    DATA_DIR=/app/data \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5000

# Install runtime dependencies including gosu for user switching
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and data directories
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data/db /app/data/config /app/data/charts /app/data/logs /app/data/archive \
    && chown -R appuser:appuser /app

# Copy Python packages from builder stage to root location for easier access
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY . .

# Keep running as root for now to avoid permission issues on Windows
# USER appuser

# Make sure scripts are executable and update PATH for root
ENV PATH=/root/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]