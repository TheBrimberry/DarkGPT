FROM python:3.11-slim

# FFmpeg for MoviePy encoding + fonts for captions
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg fonts-dejavu-core && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT=8080
EXPOSE 8080
# single worker, long timeout — renders are slow; concurrency via the worker's threads
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT} --workers 1 --threads 4 --timeout 600"]
