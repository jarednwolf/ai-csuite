
FROM python:3.12.5-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY apps/orchestrator/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY apps/orchestrator /app
COPY blueprints /app/blueprints
ENV PYTHONPATH=/app

EXPOSE 8000
CMD ["uvicorn","orchestrator.app:app","--host","0.0.0.0","--port","8000"]

