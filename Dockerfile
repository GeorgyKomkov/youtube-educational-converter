# Этап сборки
FROM python:3.9-slim as builder

WORKDIR /app

# Установка необходимых пакетов для сборки
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wkhtmltopdf \
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

# Устанавливаем ffmpeg и wkhtmltopdf в финальном контейнере
RUN apt-get update && apt-get install -y ffmpeg wkhtmltopdf && rm -rf /var/lib/apt/lists/*

# Копируем виртуальное окружение
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Копируем файлы проекта
COPY . .

# Копируем start.sh отдельно и делаем его исполняемым
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Создание необходимых директорий
RUN mkdir -p output cache torch && chmod 777 output cache torch

# Запуск приложения
CMD ["/bin/bash", "/app/start.sh"]
