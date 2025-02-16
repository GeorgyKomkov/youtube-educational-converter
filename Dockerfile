# Используем официальный образ Python 3.10
FROM python:3.10

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt . 

# Устанавливаем системные зависимости и очищаем кеш APT
RUN apt-get update && apt-get install -y \
    libsndfile1 ffmpeg wkhtmltopdf && \
    rm -rf /var/lib/apt/lists/*

# Устанавливаем Python-зависимости без кеширования
RUN pip install --no-cache-dir -r requirements.txt

# Удаляем кеши pip и временные файлы
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Устанавливаем `transformers` и `whisper` (без кеша)
RUN pip install --no-cache-dir transformers openai-whisper

# Копируем весь проект в контейнер
COPY . .

# Делаем стартовый скрипт исполняемым
RUN chmod +x start.sh

# Устанавливаем переменные окружения
ENV PYTHONPATH="/app/src"

# Открываем порт
EXPOSE 8080

# Запускаем приложение
CMD ["./start.sh"]
