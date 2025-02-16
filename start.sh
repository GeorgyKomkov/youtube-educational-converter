#!/bin/bash
set -e  # Останавливаем скрипт при ошибках

export PYTHONPATH="/app:$PYTHONPATH"
export PORT=8080

echo "Current directory: $(pwd)"
echo "Listing files:"
ls -la

echo "Checking for required files..."
if [ ! -f "client_secrets.json" ]; then
    echo "ERROR: client_secrets.json not found!"
    exit 1
fi

if [ ! -f "api.txt" ]; then
    echo "ERROR: api.txt not found!"
    exit 1
fi

echo "Starting Flask server..."
cd /app
python3 -m src.server &
SERVER_PID=$!

echo "Waiting for server to start..."
sleep 15

echo "Checking server health..."
if ! curl -v http://localhost:8080/health; then
    echo "ERROR: Server failed to start!"
    docker-compose logs
    exit 1
fi

echo "Server started successfully!"
wait $SERVER_PID
