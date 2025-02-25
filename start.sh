#!/bin/bash
set -e

# Функция очистки
cleanup() {
    echo "Cleaning up..."
    # Остановка всех фоновых процессов
    kill $(jobs -p) 2>/dev/null || true
}

# Регистрируем функцию очистки
trap cleanup EXIT

# Создаем необходимые директории (добавляем config в существующий список)
mkdir -p /app/temp /app/output /app/videos /app/logs /app/cache /app/config

# Устанавливаем права (добавляем config в существующий список)
chmod -R 777 /app/temp /app/output /app/videos /app/logs /app/cache /app/config

# Проверяем наличие необходимых переменных окружения
required_vars=("YOUTUBE_API_KEY")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: $var is not set"
        exit 1
    fi
done

# Проверяем наличие необходимых файлов
required_files=("config/config.yaml" "config/logging.yaml")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo "Error: $file not found"
        exit 1
    fi
done

# Запускаем Gunicorn с настройками
exec gunicorn --bind 0.0.0.0:8080 \
    --workers ${MAX_WORKERS:-2} \
    --threads 4 \
    --timeout 120 \
    --access-logfile /app/logs/access.log \
    --error-logfile /app/logs/error.log \
    --capture-output \
    --enable-stdio-inheritance \
    src.server:app

trap 'exit 0' SIGTERM