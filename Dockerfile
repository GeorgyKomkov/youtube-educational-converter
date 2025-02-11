# Используем официальный образ Python
FROM python:3.9-slim

# Создаем рабочую директорию
WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    ffmpeg \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Копируем только requirements.txt
COPY requirements.txt .

# Устанавливаем зависимости группами
RUN pip install --no-cache-dir \
    flask gunicorn PyYAML==6.0.1 yt-dlp \
    && rm -rf ~/.cache/pip/*

RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu \
    && rm -rf ~/.cache/pip/*

RUN pip install --no-cache-dir \
    transformers sentence-transformers \
    && rm -rf ~/.cache/pip/*

RUN pip install --no-cache-dir \
    Pillow opencv-python-headless whisper \
    && rm -rf ~/.cache/pip/*

RUN pip install --no-cache-dir \
    pdfkit markdown2 python-slugify \
    && rm -rf ~/.cache/pip/*

# Копируем остальные файлы
COPY . .

# Создаем необходимые директории
RUN mkdir -p /app/output /app/tmp

# Даем права на выполнение start.sh
RUN chmod +x start.sh

# Добавляем текущую директорию в PYTHONPATH
ENV PYTHONPATH="/app"

# Указываем порт (можно изменить через переменные окружения)
ENV PORT=8080

# Открываем порт
EXPOSE 8080

# Запускаем приложение
CMD ["./start.sh"]