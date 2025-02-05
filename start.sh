#!/bin/bash
echo "Настройка окружения..."
ffmpeg -version  # Проверяем, установлен ли FFmpeg

echo "Запуск приложения..."
python src/main.py