# Используем официальный образ Python 3.9-slim
FROM python:3.9-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаём директории
RUN mkdir -p /app/videos /app/output /app/temp /app/cache/models /app/logs && \
    chmod 777 /app/videos /app/output /app/temp /app/cache/models /app/logs

# Проверяем наличие файлов конфигурации
RUN test -f /app/client_secrets.json || echo "Warning: client_secrets.json not found"
RUN test -f /app/api.txt || echo "Warning: api.txt not found"

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=src/server.py

# Проверяем работоспособность
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Запускаем приложение
CMD ["python", "src/server.py"]
