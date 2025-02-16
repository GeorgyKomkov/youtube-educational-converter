#!/bin/bash
export PYTHONPATH="/app:$PYTHONPATH"
export MALLOC_ARENA_MAX=2  # Ограничиваем максимальное использование памяти Python
export OMP_NUM_THREADS=1    # Ограничиваем потоки OpenMP (Whisper)
export TOKENIZERS_PARALLELISM=false  # Запрещаем многопотоковость для токенизаторов

PORT=${PORT:-8080}
echo "Запуск сервера Flask на порту $PORT..."

# Фоновая очистка временных файлов (старше 1 часа) - Запускаем после сервера
(sleep 10 && while true; do
    find /app/videos -type f -mmin +60 -delete
    sleep 600
done) &

# Запускаем Flask напрямую (без Gunicorn)
cd /app/src
python3 server.py