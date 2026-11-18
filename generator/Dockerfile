FROM python:3.11-slim
WORKDIR /app
COPY generator/generate_logs.py /app/generate_logs.py
VOLUME ["/var/log/app"]
ENTRYPOINT ["python", "/app/generate_logs.py"]
CMD ["--rate", "20", "--out", "/var/log/app/app.log"]
