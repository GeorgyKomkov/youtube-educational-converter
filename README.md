# YouTube Educational Converter
перейти на сайт [(http://134.209.245.96:8080/)](http://134.209.245.96:8080/)
Приложение для преобразования образовательных YouTube видео в структурированные учебные материалы с текстом и ключевыми изображениями.

## Описание

Приложение автоматически:
1. Скачивает видео с YouTube
2. Преобразует речь в текст с помощью Whisper
3. Извлекает ключевые кадры
4. Создает PDF-документ с текстом и изображениями.




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

## Установка

1. Клонируйте репозиторий:
bash
git clone https://github.com/your-username/youtube-educational-converter.git
cd youtube-educational-converter
