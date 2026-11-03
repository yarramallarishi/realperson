FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY omnibot ./omnibot
COPY alembic.ini .
COPY migrations ./migrations
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "alembic upgrade head && uvicorn omnibot.api.main:app --host 0.0.0.0 --port 8000"]
