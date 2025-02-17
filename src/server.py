from flask import (
    Flask, 
    request, 
    jsonify, 
    render_template_string, 
    redirect, 
    session, 
    url_for
)
import os
import secrets
import threading
import logging
from datetime import datetime
import time
from celery import Celery
import redis
import yt_dlp
import psutil
import yaml
import shutil

# Импортируем недостающие модули
from src.youtube_api import YouTubeAPI
from src.process_video import process_video

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

VIDEO_DIR = "/app/videos"
OUTPUT_DIR = "/app/output"

# Загрузка конфигурации
def load_config():
    try:
        with open('config/config.yaml', 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {
            'temp_dir': '/app/temp',
            'memory': {
                'emergency_cleanup_threshold': 85
            }
        }

config = load_config()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev')

# Улучшенная конфигурация Celery
celery = Celery('youtube_converter')
celery.conf.update(
    broker_url=os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0'),
    result_backend=os.environ.get('REDIS_URL', 'redis://redis:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Улучшенные настройки для надежности
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=3600,  # 1 час максимум на задачу
    task_soft_time_limit=3300,  # 55 минут софт-лимит
    
    # Настройки ретраев
    task_routes={
        'src.server.process_video_task': {
            'queue': 'video_processing',
            'routing_key': 'video.process'
        }
    },
    broker_transport_options={
        'visibility_timeout': 3600,
        'max_retries': 3,
        'interval_start': 0,
        'interval_step': 0.2,
        'interval_max': 0.5,
    }
)

# Подключение к Redis
redis_client = redis.from_url(os.environ.get('REDIS_URL', 'redis://redis:6379/0'))

# 🔹 HTML-страница
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Video Downloader</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .alert { padding: 10px; margin-bottom: 15px; border-radius: 4px; }
        .error { background-color: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
        .success { background-color: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
        input[type="text"] { width: 100%; padding: 8px; margin: 10px 0; }
        button { padding: 8px 16px; background: #007bff; color: white; border: none; cursor: pointer; }
        button:hover { background: #0056b3; }
    </style>
</head>
<body>
    <h2>YouTube Video Downloader</h2>
    
    {% if error_message %}
    <div class="alert error">{{ error_message }}</div>
    {% endif %}
    
    {% if success_message %}
    <div class="alert success">{{ success_message }}</div>
    {% endif %}
    
    <h3>Введите ссылку на YouTube</h3>
    <form action="/download" method="post">
        <input type="text" name="url" placeholder="https://www.youtube.com/watch?v=..." required>
        <button type="submit">Получить ссылку</button>
    </form>

    {% if download_url %}
        <h3>Ваша ссылка на скачивание:</h3>
        <a href="{{ download_url }}" target="_blank">{{ download_url }}</a>
    {% endif %}
</body>
</html>
"""

# Инициализация YouTube API
youtube_api = YouTubeAPI()

@celery.task(bind=True, 
             max_retries=3, 
             retry_backoff=True,
             retry_backoff_max=600,
             rate_limit='2/m')
def process_video_task(self, video_url):
    try:
        video_id = video_url.split("v=")[-1]
        download_url, title = youtube_api.get_download_url(video_id)

        if not download_url:
            raise Exception("Failed to get download URL")

        video_path = os.path.join(VIDEO_DIR, f"{video_id}.mp4")
        ydl_opts = {
            'format': 'worst[ext=mp4]',
            'outtmpl': video_path,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'prefer_ffmpeg': True,
            'keepvideo': False,
            'max_filesize': 100 * 1024 * 1024,
            'postprocessor_args': [
                '-vf', 'scale=640:360',
                '-b:v', '500k',
                '-maxrate', '500k',
                '-bufsize', '1000k',
                '-b:a', '128k',
            ],
            'no_check_certificate': True,
            'ignoreerrors': True,
            'no_warnings': True,
            'quiet': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'player_skip': ['webpage', 'config', 'js']
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate'
            }
        }

        logger.info(f"Starting download for video {video_id}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        return {"status": "success", "video_path": video_path}

    except Exception as exc:
        logger.error(f"Error processing video: {exc}")
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            raise self.retry(exc=exc, countdown=2 ** retry_count)
        raise

@app.route("/", methods=["GET"])
def index():
    logger.debug("Запрошена главная страница")
    # Получаем сообщения из сессии
    error_message = session.pop('error_message', None)
    success_message = session.pop('success_message', None)
    download_url = session.pop('download_url', None)
    
    return render_template_string(HTML_PAGE, 
                                 download_url=download_url,
                                 error_message=error_message,
                                 success_message=success_message)

@app.route('/auth')
def auth():
    logger.info("Начата OAuth аутентификация")
    """Инициирует OAuth2 аутентификацию"""
    try:
        youtube_api.authenticate()
        return redirect(url_for('index'))
    except Exception as e:
        session['error_message'] = f"Ошибка аутентификации: {str(e)}"
        return redirect(url_for('index'))

@app.route("/download", methods=["POST"])
def download_video():
    logger.info("Получен запрос на скачивание видео")
    video_url = request.form.get("url")
    
    if not video_url:
        logger.warning("URL не предоставлен")
        return jsonify({"error": "URL обязателен"}), 400

    try:
        logger.info(f"Начинаем обработку видео: {video_url}")
        video_id = video_url.split("v=")[-1]
        
        # Запускаем асинхронную задачу
        task = process_video_task.delay(video_url)
        
        session['success_message'] = f"Видео поставлено в очередь на обработку. ID задачи: {task.id}"
        return redirect(url_for('index'))

    except Exception as e:
        logger.error(f"Ошибка при обработке видео: {e}")
        session['error_message'] = f"Ошибка: {str(e)}"
        return redirect(url_for('index'))

@app.route("/health")
def health_check():
    """Эндпоинт для проверки работоспособности сервера"""
    try:
        # Проверка подключения к Redis
        redis_client.ping()
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "redis": "connected"
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

def cleanup_old_files():
    logger.info("Запущена очистка старых файлов")
    """Очистка старых временных файлов"""
    while True:
        try:
            for dir_path in [VIDEO_DIR, OUTPUT_DIR]:
                for file in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, file)
                    if time.time() - os.path.getmtime(file_path) > 24*60*60:  # 24 часа
                        os.remove(file_path)
        except Exception as e:
            logger.error(f"Ошибка при очистке файлов: {e}")
        time.sleep(3600)  # Проверка каждый час

# Запускаем очистку в отдельном потоке
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

def ensure_directories():
    """Проверяет и создает необходимые директории"""
    directories = [
        VIDEO_DIR,
        OUTPUT_DIR,
        "/app/temp",
        "/app/cache/models",
        "/app/logs"
    ]
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Directory {directory} is ready")
        except Exception as e:
            logger.error(f"Failed to create directory {directory}: {e}")
            raise

def cleanup_temp(temp_dir):
    """Очистка временных файлов"""
    try:
        if os.path.exists(temp_dir):
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    logger.error(f"Error cleaning up {file_path}: {e}")
        logger.info(f"Cleaned up temporary directory: {temp_dir}")
    except Exception as e:
        logger.error(f"Error in cleanup_temp: {e}")

def monitor_resources():
    while True:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        logger.info(f"Resource usage: CPU {cpu_percent}%, RAM {memory.percent}%, Disk {disk.percent}%")
        
        if memory.percent > config['memory']['emergency_cleanup_threshold'] or disk.percent > 85:
            logger.warning("Resource usage critical! Performing emergency cleanup...")
            cleanup_temp(config['temp_dir'])
            
        time.sleep(60)  # Проверка каждую минуту

# Запускаем мониторинг в отдельном потоке
monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
monitor_thread.start()

if __name__ == "__main__":
    ensure_directories()
    port = int(os.environ.get("PORT", 8080))
    
    # Конфигурация для экономии памяти
    options = {
        'worker_class': 'gthread',
        'workers': 1,
        'threads': 2,
        'timeout': 120,
        'max_requests': 1000,
        'max_requests_jitter': 50
    }
    
    app.run(host="0.0.0.0", port=port)
