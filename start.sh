#!/bin/bash
echo "Запуск приложения на порту $PORT..."
gunicorn --bind 0.0.0.0:$PORT src.main:app