FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir asyncpg==0.29.0
COPY anomaly/detector.py /app/detector.py
CMD ["python", "/app/detector.py"]
