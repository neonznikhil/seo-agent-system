FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Stage source from build context (works seamlessly whether context is '.' or 'backend')
COPY . /tmp/src/

# Install requirements from whichever path exists
RUN if [ -f /tmp/src/backend/requirements.txt ]; then \
        pip install --no-cache-dir -r /tmp/src/backend/requirements.txt; \
    else \
        pip install --no-cache-dir -r /tmp/src/requirements.txt; \
    fi

# Ensure /app/backend is cleanly populated with backend files and main.py
RUN mkdir -p /app/backend/local_data && \
    if [ -d /tmp/src/backend ]; then \
        cp -r /tmp/src/backend/* /app/backend/ && \
        (cp -r /tmp/src/backend/.[!.]* /app/backend/ 2>/dev/null || true); \
    fi && \
    cp -f /tmp/src/main.py /app/backend/main.py && \
    cp -f /tmp/src/config.py /app/backend/config.py && \
    (cp -f /tmp/src/error_handling.py /app/backend/error_handling.py 2>/dev/null || true) && \
    rm -rf /tmp/src

ENV PYTHONPATH="/app:/app/backend"
WORKDIR /app/backend

EXPOSE 10000

CMD ["sh", "-c", "cd /app/backend && uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
