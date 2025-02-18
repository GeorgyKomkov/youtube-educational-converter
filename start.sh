#!/bin/bash
set -e

# Очистка временных файлов
cleanup() {
    echo "Cleaning up..."
    rm -rf /tmp/* /var/tmp/*
    docker system prune -af --volumes
}

# Регистрируем функцию очистки
trap cleanup EXIT

# Создание необходимых директорий
directories=(
    "/app/videos"
    "/app/output"
    "/app/temp"
    "/app/cache/models"
    "/app/logs"
)

for dir in "${directories[@]}"; do
    mkdir -p "$dir"
    chmod 777 "$dir"
done

# Запуск Gunicorn с метриками
exec gunicorn \
    --workers=2 \
    --threads=4 \
    --bind 0.0.0.0:${PORT:-8080} \
    --timeout 120 \
    --log-level info \
    src.server:app
