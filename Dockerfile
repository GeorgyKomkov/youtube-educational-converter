# Используем официальный образ Python
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    wkhtmltopdf \
    gcc \
    python3-dev \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Копируем только необходимые файлы
COPY requirements.txt .
COPY start.sh .

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальные файлы проекта
COPY . .

# Создаём директории и устанавливаем права
RUN mkdir -p /app/videos /app/output /app/temp /app/cache/models /app/logs && \
    chmod -R 777 /app/videos /app/output /app/temp /app/cache /app/logs && \
    chmod +x start.sh

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app \
    FLASK_APP=src.server \
    PYTHONUNBUFFERED=1

# Создаем непривилегированного пользователя
RUN useradd -m appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["./start.sh"]