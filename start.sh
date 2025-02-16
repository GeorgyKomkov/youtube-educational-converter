#!/bin/bash
export PYTHONPATH="/app:$PYTHONPATH"
export PORT=8080
echo "Запуск сервера Flask на порту $PORT..."

# Фоновая очистка временных файлов
(sleep 10 && while true; do
    find /app/videos -type f -mmin +60 -delete
    sleep 600
done) &

# Запускаем Flask напрямую с логами
cd /app/src
exec python3 server.py
