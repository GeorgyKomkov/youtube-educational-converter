# Используем Python 3.10
FROM python:3.10

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем и устанавливаем зависимости отдельно (чтобы кешировалось)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код
COPY . .

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1

# Запускаем сервер через Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "src.server:app"]

