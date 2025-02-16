# Используем официальный образ Python 3.10
FROM python:3.10

# Устанавливаем рабочую директорию
WORKDIR /app

# Создаём директорию для хранения видео и даём нужные права
RUN mkdir -p /app/videos && chmod 777 /app/videos

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем системные зависимости (FFmpeg нужен для обработки аудио)
RUN apt-get update && apt-get install -y \
    libsndfile1 ffmpeg wkhtmltopdf && \
    rm -rf /var/lib/apt/lists/*

# Устанавливаем Python-зависимости поэтапно (ускоряет кеширование)
RUN pip install --no-cache-dir flask yt-dlp requests pydub
RUN pip install --no-cache-dir numpy opencv-python
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir openai-whisper transformers

# Отключаем многопоточность, чтобы снизить нагрузку на слабый сервер
ENV TOKENIZERS_PARALLELISM=false
ENV OMP_NUM_THREADS=1

# Копируем весь проект
COPY . .

# Исправляем проблему Windows CRLF → LF
RUN sed -i 's/\r$//' /app/start.sh

# Делаем `start.sh` исполняемым
RUN chmod +x /app/start.sh

# Запускаем через `bash`, чтобы избежать ошибки `no such file or directory`
CMD ["/bin/bash", "/app/start.sh"]
