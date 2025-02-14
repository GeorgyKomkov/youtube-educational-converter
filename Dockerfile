# Используем CUDA-совместимый базовый образ для поддержки GPU
FROM pytorch/pytorch:2.0.0-cuda11.7-cudnn8-runtime

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements первым для использования кеша Docker
COPY requirements.txt .

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r requirements.txt

# Создаем необходимые директории
RUN mkdir -p output cache torch config

# Копируем конфигурационные файлы первыми
COPY config/config.yaml config/

# Копируем остальные файлы приложения
COPY . .

# Устанавливаем переменные окружения
ENV PYTHONPATH=/app
ENV TORCH_HOME=/app/torch
ENV TRANSFORMERS_CACHE=/app/cache
ENV HF_HOME=/app/cache

# Делаем start.sh исполняемым
RUN chmod +x start.sh

# Команда по умолчанию (будет переопределена в docker-compose)
CMD ["./start.sh"]