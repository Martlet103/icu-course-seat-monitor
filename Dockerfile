FROM python:3.12-alpine

WORKDIR /app
COPY monitor.py /app/monitor.py

ENTRYPOINT ["python", "/app/monitor.py"]
