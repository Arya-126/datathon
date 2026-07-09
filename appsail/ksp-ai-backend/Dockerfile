# Catalyst AppSail — custom OCI runtime for FastAPI + SQLite.
# Falls back to bundled SQLite when Catalyst Data Store env vars are absent.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App source.
COPY . .

# AppSail routes HTTP to the port exposed here.
EXPOSE 9000

# Seed the SQLite DB at container start if it's not already present, then
# launch uvicorn. Catalyst injects PORT via X_ZOHO_CATALYST_LISTEN_PORT
# when using its managed router — we bind to $PORT if provided else 9000.
CMD ["sh", "-c", "python -c 'from seed import seed; seed()' && python -m uvicorn main:app --host 0.0.0.0 --port ${X_ZOHO_CATALYST_LISTEN_PORT:-9000}"]
