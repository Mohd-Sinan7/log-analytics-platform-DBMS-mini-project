FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY api/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY api/ /app/api/
COPY ingest/_es_setup.py /app/ingest/_es_setup.py
COPY ingest/__init__.py /app/ingest/__init__.py
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
