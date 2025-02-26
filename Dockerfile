# Используем более легкий базовый образ
FROM python:3.9-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    curl \
    git \
    ffmpeg \
    wkhtmltopdf \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

# Обновление pip
RUN pip install --upgrade pip

# Создание директорий
RUN mkdir -p /app/{temp,output,videos,cache,logs}

WORKDIR /app

# Копирование файлов
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование остальных файлов
COPY . .

# Установка прав
RUN chmod -R 755 /app && \
    chmod 777 /app/{temp,output,videos,cache,logs}

CMD ["./start.sh"]