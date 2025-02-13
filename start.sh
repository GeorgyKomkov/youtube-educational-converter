#!/bin/bash
PORT=${PORT:-8080}
echo "Запуск приложения на порту $PORT..."

# Запускаем Flask-приложение
cd /app/src && gunicorn --bind 0.0.0.0:$PORT main:app &

# Запускаем Celery-воркер
cd /app && celery -A celery worker --loglevel=info &

# Ожидание процессов
wait
