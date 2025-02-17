# Используем официальный образ Python 3.9-slim
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаём директории
RUN mkdir -p /app/videos /app/output /app/temp /app/cache/models /app/logs && \
    chmod -R 777 /app/videos /app/output /app/temp /app/cache /app/logs

# Копируем весь проект
COPY . .

# Проверяем наличие файлов конфигурации
RUN ls -la /app && \
    test -d /app/src || (echo "Source directory not found" && exit 1)

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=src.server
ENV PYTHONPATH=/app

EXPOSE 8080

# Проверяем работоспособность
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Запускаем приложение
CMD ["python", "src/server.py"]
