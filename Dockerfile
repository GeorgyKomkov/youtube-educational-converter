# Используем официальный образ Python 3.9-slim
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    wkhtmltopdf \
    gcc \
    python3-dev \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Копируем файлы проекта
COPY requirements.txt .

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir gunicorn

# Копируем остальные файлы
COPY src/ /app/src/
COPY config/ /app/config/

# Создаём директории
RUN mkdir -p /app/videos /app/output /app/temp /app/cache/models /app/logs && \
    chmod -R 777 /app/videos /app/output /app/temp /app/cache /app/logs

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=src.server
ENV PYTHONPATH=/app

EXPOSE 8080

# Убираем HEALTHCHECK, так как он теперь в docker-compose
# Убираем CMD, так как он теперь в docker-compose
