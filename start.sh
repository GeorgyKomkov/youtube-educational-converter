#!/bin/bash
set -e

# Создаем необходимые директории
mkdir -p /app/temp /app/output /app/videos /app/logs /app/cache

# Устанавливаем права
chmod -R 777 /app/temp /app/output /app/videos /app/logs /app/cache

# Запускаем Gunicorn
exec gunicorn --bind 0.0.0.0:8080 \
    --workers 2 \
    --threads 4 \
    --timeout 120 \
    --access-logfile /app/logs/access.log \
    --error-logfile /app/logs/error.log \
    src.server:app

# Файл должен быть исполняемым
chmod +x start.sh

trap 'exit 0' SIGTERM
