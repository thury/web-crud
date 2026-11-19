FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Usuario sin privilegios; data/ y staticfiles/ le pertenecen para que SQLite pueda escribir
RUN adduser --disabled-password --no-create-home appuser \
    && mkdir -p /app/data /app/staticfiles \
    && chown -R appuser /app/data /app/staticfiles \
    && chmod +x /app/entrypoint.sh

USER appuser
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
