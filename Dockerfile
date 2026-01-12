FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /tmp/autocut/uploads /tmp/autocut/outputs /tmp/autocut/processing

EXPOSE 8000

CMD ["python", "main.py"]
```

---

### 2. **requirements.txt** :
```
fastapi==0.109.0
uvicorn==0.27.0
python-multipart==0.0.6
pydantic==2.5.3
aiofiles==23.2.1
