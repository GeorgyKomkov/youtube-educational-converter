#!/bin/bash
set -ex

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

# Проверка переменных окружения
if [ -z "$YOUTUBE_API_KEY" ]; then
    echo "ERROR: YOUTUBE_API_KEY not set"
    exit 1
fi

exec python3 -m flask --app src.server run --host=0.0.0.0 --port=8080 --debug
