from celery import Celery
import os
import yaml
from src.video_converter import VideoConverter
from sentence_transformers import SentenceTransformer
import whisper

# ✅ Загружаем конфигурацию
try:
    with open('/app/config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
except Exception as e:
    print(f"Ошибка загрузки конфигурации: {e}")
    config = {}

# ✅ Устанавливаем кеш моделей
CACHE_DIR = config.get("model_cache", "/app/cache/models")
os.environ["TRANSFORMERS_CACHE"] = CACHE_DIR
os.environ["HF_HOME"] = CACHE_DIR
print(f"Используется кеш моделей: {CACHE_DIR}")

# ✅ Настройка Celery
celery = Celery(
    'tasks',
    broker=config['celery']['broker_url'],
    backend=config['celery']['backend_url']
)

# ✅ Кешируем модели
print("Загрузка моделей для Celery...")
whisper_model = whisper.load_model(config.get('transcription', {}).get('model', 'medium'))
text_model = SentenceTransformer('all-MiniLM-L6-v2')
print("Модели загружены.")

# ✅ Создаём объект VideoConverter
video_converter = VideoConverter(config)

@celery.task
def process_video(url):
    """Фоновая задача для обработки видео"""
    return video_converter.convert(url)
