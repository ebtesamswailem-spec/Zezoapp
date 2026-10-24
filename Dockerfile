FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg aria2 nodejs && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -U -r requirements.txt
COPY app.py .
CMD pip install --no-cache-dir -U "yt-dlp[default]" && gunicorn -b 0.0.0.0:${PORT:-8000} -w 2 --threads 4 --timeout 0 app:app
