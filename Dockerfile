FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Render injects $PORT; gunicorn binds to it at container start.
# Timeout bumped up since /download now does real work (download + ffmpeg
# merge) rather than just resolving a link — some videos will take a while.
CMD gunicorn --bind 0.0.0.0:$PORT --timeout 300 --workers 1 app:app
