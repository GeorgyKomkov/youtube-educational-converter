# Используем официальный образ Python 3.10
FROM python:3.10

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем системные зависимости (FFmpeg нужен для обработки аудио)
RUN apt-get update && apt-get install -y \
    libsndfile1 ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Устанавливаем Python-зависимости поэтапно (ускоряет кеширование)
RUN pip install --no-cache-dir flask yt-dlp requests pydub
RUN pip install --no-cache-dir numpy opencv-python
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir openai-whisper transformers

# Отключаем многопоточность, чтобы снизить нагрузку на слабый сервер
ENV TOKENIZERS_PARALLELISM=false
ENV OMP_NUM_THREADS=1

# Копируем весь проект в контейнер
COPY . .

# Делаем стартовый скрипт исполняемым
RUN chmod +x start.sh

# Запускаем приложение
CMD ["./start.sh"]
