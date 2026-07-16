FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY app ./app

RUN mkdir -p /app/data /app/config /app/logs

EXPOSE 8080

CMD ["uvicorn", "app.web.app:app", "--host", "0.0.0.0", "--port", "8080"]
