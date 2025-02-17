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

# Проверка версии Python
python3 --version | grep -q "Python 3.[91]" || {
    echo "ERROR: Required Python 3.9 or higher"
    exit 1
}

# Проверка системных зависимостей
command -v ffmpeg >/dev/null 2>&1 || {
    echo "ERROR: ffmpeg is required but not installed"
    exit 1
}

command -v wkhtmltopdf >/dev/null 2>&1 || {
    echo "ERROR: wkhtmltopdf is required but not installed"
    exit 1
}

# Проверка обязательных переменных окружения
required_vars=(
    "REDIS_URL"
    "CELERY_BROKER_URL"
    "FLASK_APP"
    "PYTHONPATH"
    "YOUTUBE_API_KEY"
)

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "ERROR: $var is not set"
        exit 1
    fi
done

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

export PYTHONPATH="/app:$PYTHONPATH"
export PORT=8080

echo "Current directory: $(pwd)"
echo "Python version and location:"
which python3
python3 --version

echo "Listing directory contents:"
ls -la /app/

echo "Checking for required files..."
for file in "/app/client_secrets.json" "/app/api.txt"; do
    if [ ! -f "$file" ]; then
        echo "ERROR: $file not found!"
        echo "Directory contents:"
        ls -la /app/
        echo "Mount points:"
        mount | grep app
        exit 1
    fi
done

echo "Checking file permissions:"
ls -la /app/client_secrets.json /app/api.txt

echo "Checking disk space:"
df -h

echo "Starting Flask server..."
cd /app

exec python3 -m flask --app src.server run --host=0.0.0.0 --port=8080 --debug
