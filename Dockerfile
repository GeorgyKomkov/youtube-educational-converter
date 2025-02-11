# Этап сборки
FROM python:3.9-slim as builder

WORKDIR /app

# Установка необходимых пакетов для сборки
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Копируем только requirements.txt
COPY requirements.txt .

# Устанавливаем зависимости в виртуальное окружение
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Финальный этап
FROM python:3.9-slim

WORKDIR /app

# Копируем ffmpeg
COPY --from=builder /usr/bin/ffmpeg /usr/bin/ffmpeg
COPY --from=builder /usr/bin/ffprobe /usr/bin/ffprobe

# Копируем виртуальное окружение
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Копируем файлы проекта
COPY . .

# Создание необходимых директорий
RUN mkdir -p output cache torch && \
    chmod 777 output cache torch && \
    chmod +x start.sh

# Запуск приложения
CMD ["./start.sh"]