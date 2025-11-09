# Use Python 3.12 slim image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies for PostGIS/geospatial libraries
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code (all backend files are in backend/ directory)
COPY backend/ ./backend/

# Set working directory to backend for imports to work correctly
WORKDIR /app/backend

# Expose port
EXPOSE $PORT

# Start the application
CMD uvicorn api_server:api_app --host 0.0.0.0 --port ${PORT:-8000}

