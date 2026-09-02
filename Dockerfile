FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend into /app/backend and set PYTHONPATH so both `backend.xxx` and `xxx` imports resolve
COPY backend/ /app/backend/
RUN mkdir -p /app/backend/local_data

ENV PYTHONPATH="/app:/app/backend"
WORKDIR /app/backend

# Expose port for Fly.io and Render
EXPOSE 8080

# Use PORT env var (Render sets this to 10000, Fly.io sets to 8080)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
