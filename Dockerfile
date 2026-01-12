FROM python:3.11-slim

# Install ALL build dependencies (gcc needed for PyAV compilation)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    pkg-config \
    gcc \
    build-essential \
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
