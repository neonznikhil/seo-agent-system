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

COPY backend/ .
COPY run_backend.py .
RUN mkdir -p local_data

# Expose port for Render
EXPOSE 10000

# Run with wrapper script
CMD ["python", "run_backend.py"]
