FROM python:3.11-slim
WORKDIR /app
COPY ingest/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY ingest/ /app/ingest/
COPY ingest/agent.py /app/agent.py
ENV PYTHONPATH=/app
CMD ["python", "-m", "ingest.agent"]
