#!/bin/bash
echo "Запуск приложения на порту $PORT..."
echo "Текущая директория: $(pwd)"
echo "Содержимое директории src:"
ls -la src/
gunicorn --bind 0.0.0.0:$PORT src.main:app