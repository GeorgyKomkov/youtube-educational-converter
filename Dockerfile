# Используем официальный образ Python
FROM python:3.9-slim

# Создаем рабочую директорию
WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Копирование файлов проекта
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создание необходимых директорий
RUN mkdir -p output cache torch
RUN chmod 777 output cache torch

# Делаем start.sh исполняемым
RUN chmod +x start.sh

# Запуск приложения
CMD ["./start.sh"]