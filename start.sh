#!/bin/bash
set -ex  # Добавляем -x для вывода выполняемых команд

export PYTHONPATH="/app:$PYTHONPATH"
export PORT=8080

echo "Current directory: $(pwd)"
echo "Listing files:"
ls -la

echo "Python version:"
python3 --version

echo "Checking for required files..."
if [ ! -f "client_secrets.json" ]; then
    echo "ERROR: client_secrets.json not found!"
    ls -la /app/
    exit 1
fi

if [ ! -f "api.txt" ]; then
    echo "ERROR: api.txt not found!"
    ls -la /app/
    exit 1
fi

echo "Starting Flask server..."
cd /app
python3 -m src.server &
SERVER_PID=$!

echo "Waiting for server to start..."
sleep 20

echo "Checking server health..."
if ! curl -v http://localhost:8080/health; then
    echo "ERROR: Server failed to start!"
    echo "Process list:"
    ps aux
    echo "Network status:"
    netstat -tulpn
    echo "Container logs:"
    docker-compose logs
    exit 1
fi

echo "Server started successfully!"
wait $SERVER_PID
