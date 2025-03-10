# Используем более легкий базовый образ
FROM python:3.9-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    ffmpeg \
    curl \
    wkhtmltopdf \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

# Обновление pip
RUN pip install --upgrade pip

# Создание директорий (исправленный синтаксис)
RUN mkdir -p /app/temp /app/output /app/videos /app/cache /app/logs /app/config

WORKDIR /app

# Копирование файлов
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем youtube-dl и yt-dlp
RUN pip3 install --no-cache-dir youtube-dl yt-dlp

# Копирование остальных файлов
COPY . .

# Установка прав (исправленный синтаксис)
RUN chmod -R 755 /app && \
    chmod 777 /app/temp /app/output /app/videos /app/cache /app/logs /app/config

CMD ["./start.sh"]