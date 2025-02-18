# Используем более легкий базовый образ
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем только необходимые системные зависимости
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wkhtmltopdf \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

# Копируем только requirements.txt
COPY requirements.txt .

# Оптимизируем установку pip пакетов
RUN pip install --no-cache-dir -r requirements.txt

# Копируем остальные файлы
COPY . .

# Создаём директории и устанавливаем права
RUN mkdir -p /app/videos /app/output /app/temp /app/cache/models /app/logs && \
    chmod -R 777 /app/videos /app/output /app/temp /app/cache /app/logs && \
    chmod +x /app/start.sh

# Переменные окружения
ENV PYTHONPATH=/app \
    FLASK_APP=src.server \
    PYTHONUNBUFFERED=1

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["./start.sh"]