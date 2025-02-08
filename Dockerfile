# Используем официальный образ Python
FROM python:3.9-slim

# Устанавливаем FFmpeg (обязательно!)
RUN apt-get update && apt-get install -y ffmpeg

# Создаем рабочую директорию
WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Даем права на выполнение start.sh
RUN chmod +x start.sh

# Указываем порт (можно изменить через переменные окружения)
ENV PORT=5000

# Запускаем приложение
CMD ["bash", "start.sh"]