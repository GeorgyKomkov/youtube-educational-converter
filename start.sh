#!/bin/bash
export PYTHONPATH="/app:$PYTHONPATH"
export PORT=8080
echo "Запуск сервера Flask на порту $PORT..."

# Фоновая очистка временных файлов
(sleep 10 && while true; do
    find /app/videos -type f -mmin +60 -delete
    sleep 600
done) &

# Проверяем наличие необходимых файлов
if [ ! -f "client_secrets.json" ]; then
    echo "ERROR: client_secrets.json not found!"
    exit 1
fi

if [ ! -f "api.txt" ]; then
    echo "ERROR: api.txt not found!"
    exit 1
fi

# Запускаем Flask с проверкой
cd /app
python3 -m src.server &
SERVER_PID=$!

# Ждем запуска сервера
sleep 10

# Проверяем, что сервер запустился
if ! curl -s http://localhost:8080/health > /dev/null; then
    echo "ERROR: Server failed to start!"
    exit 1
fi

# Ждем завершения процесса
wait $SERVER_PID
