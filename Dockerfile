FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV PYTHONUNBUFFERED=1 \
    PORT=5000

# SQLite database lives in /app/data (mount a volume to persist it)
RUN mkdir -p /app/data
ENV DATABASE=/app/data/assist.db

EXPOSE 5000

# For production, prefer: pip install gunicorn && gunicorn -b 0.0.0.0:$PORT app:app
CMD ["sh", "-c", "python app.py"]
