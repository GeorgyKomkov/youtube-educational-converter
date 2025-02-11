#!/bin/bash
PORT=${PORT:-8080}
echo "Запуск приложения на порту $PORT..."
cd /app/src && gunicorn --bind 0.0.0.0:$PORT main:app