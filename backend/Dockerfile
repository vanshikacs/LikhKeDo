# Build from the repo root so the seeded demo cache ships in the image:
#   docker build -f backend/Dockerfile -t likhkedo-api .
FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY demo/policy ./demo/policy
COPY demo/cache ./demo/cache

ENV DATA_DIR=/tmp/likhkedo \
    DEMO_DIR=/app/demo \
    PYTHONUNBUFFERED=1

EXPOSE 8000
# --proxy-headers: Render terminates TLS (wss://) and forwards; WebSockets pass through.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
