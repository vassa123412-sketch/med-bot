FROM python:3.12-slim

WORKDIR /app

# Системные зависимости: Tesseract OCR, PostgreSQL драйвер, WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-rus \
    libpq-dev \
    gcc \
    curl \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data /app/logs

EXPOSE 8080

# FastAPI webhook (не polling)
CMD ["uvicorn", "bot.webhook:app", "--host", "0.0.0.0", "--port", "8080"]
