from celery_app import Celery
import os
import yaml
from src.video_converter import VideoConverter
from sentence_transformers import SentenceTransformer
import whisper

# Загрузка конфигурации
try:
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
except Exception as e:
    print(f"Ошибка загрузки конфигурации: {e}")
    config = {}

# Настройка Celery
celery = Celery(
    'tasks',
    broker=config['celery']['broker_url'],
    backend=config['celery']['backend_url']
)

# Кешируем модели
print("Загрузка моделей для Celery...")
whisper_model = whisper.load_model(config.get('transcription', {}).get('model', 'base'))
text_model = SentenceTransformer('all-MiniLM-L6-v2')
print("Модели загружены.")

# Создаём объект VideoConverter с кешированными моделями
video_converter = VideoConverter(config, whisper_model, text_model)

@celery.task
def process_video(url):
    """Фоновая задача для обработки видео"""
    return video_converter.convert(url)
