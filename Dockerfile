FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Render injects $PORT; gunicorn binds to it at container start.
CMD gunicorn --bind 0.0.0.0:$PORT --timeout 120 --workers 2 app:app
