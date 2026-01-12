FROM python:3.11-slim

# CRITICAL: Install pkg-config and all FFmpeg dev libraries
RUN apt-get update && apt-get install -y \
    ffmpeg \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /tmp/autocut/uploads /tmp/autocut/outputs /tmp/autocut/processing /tmp/autocut/styles

EXPOSE 8000

CMD ["python", "main.py"]
