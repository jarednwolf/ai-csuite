FROM python:3.12.5-slim

WORKDIR /app
COPY apps/worker/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/worker/worker.py /app/worker.py
CMD ["python", "/app/worker.py"]


