# YouTube Educational Converter

Приложение для преобразования образовательных YouTube видео в структурированные учебные материалы с текстом и ключевыми изображениями.

## Описание

Приложение автоматически:
1. Скачивает видео с YouTube
2. Преобразует речь в текст с помощью Whisper
3. Извлекает ключевые кадры
4. Создает PDF-документ с текстом и изображениями

## Требования

### Системные требования
- Python 3.10 или выше
- FFmpeg
- wkhtmltopdf
- 4GB RAM минимум
- 10GB свободного места на диске

### Зависимости Python
Все необходимые зависимости указаны в `requirements.txt`

## Настройка YouTube API

1. Создайте проект в [Google Cloud Console](https://console.cloud.google.com/)
2. Включите YouTube Data API v3
3. Создайте учетные данные:
   - OAuth 2.0 клиент
   - API ключ
4. Сохраните полученные данные:
   - `client_secrets.json` - для OAuth аутентификации
   - `api.txt` - для API ключа

## Запуск

### Локальный запуск

1. Активируйте виртуальное окружение:
```bash
source venv/bin/activate  # Для Linux/Mac
venv\Scripts\activate     # Для Windows
```

2. Запустите сервер:
```bash
python -m src.server
```

3. Откройте браузер:
```
http://localhost:8080
```

4. Пройдите OAuth аутентификацию через `/auth` эндпоинт

### Docker запуск

```bash
docker-compose up -d
```

## Структура проекта

```
├── src/                    # Исходный код
│   ├── server.py          # Веб-сервер
│   ├── youtube_api.py     # Работа с YouTube API
│   ├── process_video.py   # Обработка видео
│   ├── audio_extractor.py # Извлечение аудио
│   ├── frame_processor.py # Обработка кадров
│   └── output_generator.py # Генерация PDF
├── config/                 # Конфигурационные файлы
├── docker-compose.yml     # Docker конфигурация
└── requirements.txt       # Python зависимости
```

## Решение проблем

### Ошибка авторизации YouTube
1. Проверьте наличие `client_secrets.json` и `api.txt`
2. Убедитесь, что разрешения OAuth настроены правильно
3. Попробуйте переавторизоваться через `/auth`

### Ошибка при обработке видео
1. Проверьте установку FFmpeg и wkhtmltopdf
2. Убедитесь, что достаточно места на диске
3. Проверьте логи в `app.log`

## Установка

1. Клонируйте репозиторий:
bash
git clone https://github.com/your-username/youtube-educational-converter.git
cd youtube-educational-converter

2. Установите системные зависимости:

Для Ubuntu/Debian: