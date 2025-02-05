#!/bin/bash

echo "Настройка окружения..."
ffmpeg -version  # Проверяем, установлен ли FFmpeg

echo "Запуск приложения..."
python src/main.py --url "https://youtu.be/your-video-id"