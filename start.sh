#!/bin/bash
export PYTHONPATH="/app:$PYTHONPATH"
export MALLOC_ARENA_MAX=2  # Ограничиваем максимальное использование памяти Python
export OMP_NUM_THREADS=1    # Ограничиваем потоки OpenMP (Whisper)
export TOKENIZERS_PARALLELISM=false  # Запрещаем многопотоковость для токенизаторов

PORT=${PORT:-8080}
echo "Запуск приложения на порту $PORT..."

# Фоновая очистка временных файлов (старше 1 часа)
while true; do
    find /app/videos -type f -mmin +60 -delete
    sleep 600
done &

# Запускаем Flask-приложение через Gunicorn
cd /app/src && gunicorn --bind 0.0.0.0:$PORT --workers=1 --threads=1 --timeout=300 --max-requests=5 --max-requests-jitter=2 main:app &

# Ожидание процессов
wait
