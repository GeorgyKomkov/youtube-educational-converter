from flask import (
    Flask, 
    request, 
    jsonify, 
    session, 
    render_template,
    send_from_directory
)
import os
import logging
from datetime import datetime
import time
import threading
from celery import Celery
import redis
import psutil
import yaml
import shutil
from werkzeug.exceptions import NotFound
from prometheus_client import start_http_server, Counter, Histogram
import sys
import json
from apscheduler.schedulers.background import BackgroundScheduler

# Импортируем нужные модули
from src.youtube_api import YouTubeAPI
from src.process_video import process_video

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Константы
VIDEO_DIR = "/app/videos"
OUTPUT_DIR = "/app/output"
TEMP_DIR = "/app/temp"

def load_config():
    """Загрузка и валидация конфигурации"""
    try:
        with open('config/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
            
        # Проверяем обязательные параметры
        required_params = ['temp_dir', 'memory', 'server', 'storage']
        for param in required_params:
            if param not in config:
                raise ValueError(f"Missing required parameter: {param}")
                
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {
            'temp_dir': TEMP_DIR,
            'memory': {
                'emergency_cleanup_threshold': 85,
                'cleanup_interval': 3600
            },
            'server': {
                'host': '0.0.0.0',
                'port': 8080
            },
            'storage': {
                'temp_lifetime': 3600,
                'cache_size_mb': 1000,
                'cache_dir': TEMP_DIR
            }
        }

# Инициализация конфигурации
config = load_config()

# Инициализация Flask
app = Flask(__name__, 
    static_folder='static',
    template_folder='templates'
)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or os.urandom(24)

# Добавить проверку существования директорий при старте
for directory in [VIDEO_DIR, OUTPUT_DIR, TEMP_DIR]:
    try:
        os.makedirs(directory, exist_ok=True)
        os.chmod(directory, 0o777)
    except Exception as e:
        logger.error(f"Failed to create directory {directory}: {e}")
        sys.exit(1)

# Конфигурация Celery
celery = Celery('youtube_converter')
celery.conf.update(
    broker_url=os.environ.get('CELERY_BROKER_URL', 'redis://redis:6379/0'),
    result_backend=os.environ.get('REDIS_URL', 'redis://redis:6379/0'),
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=3600,
    task_soft_time_limit=3300
)

# Подключение к Redis
redis_client = redis.from_url(
    os.environ.get('REDIS_URL', 'redis://redis:6379/0'),
    decode_responses=True
)

# Инициализация YouTube API
youtube_api = YouTubeAPI()

# Метрики
REQUEST_COUNT = Counter('request_count', 'App Request Count', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('request_latency_seconds', 'Request latency')

@celery.task(bind=True)
def process_video_task(self, video_url, user_cookies=None):
    """Celery задача для обработки видео"""
    try:
        # Получаем информацию о видео
        video_info = youtube_api.get_video_info(video_url, user_cookies)
        if not video_info:
            raise ValueError("Failed to get video info")

        # Обработка видео
        result = process_video(video_info['path'])
        
        return {
            'status': 'success',
            'video_path': result['output_path'],
            'title': video_info['title']
        }
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        raise

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/api/convert', methods=['POST'])
def convert_video():
    """API endpoint для конвертации видео"""
    try:
        data = request.json
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400

        # Получаем cookies из сессии
        user_cookies = session.get('youtube_cookies')
        
        # Создаем задачу
        task = process_video_task.delay(data['url'], user_cookies)
        
        return jsonify({
            'status': 'processing',
            'task_id': task.id
        })
    except Exception as e:
        logger.error(f"Error starting conversion: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status/<task_id>')
def check_status(task_id):
    """Проверка статуса задачи"""
    try:
        task = process_video_task.AsyncResult(task_id)
        
        if task.ready():
            if task.successful():
                result = task.get()
                return jsonify({
                    'status': 'completed',
                    'video_path': result['video_path'],
                    'title': result.get('title', 'Video')
                })
            else:
                return jsonify({
                    'status': 'failed',
                    'error': str(task.result)
                })
        
        return jsonify({
            'status': 'processing',
            'progress': task.info.get('progress', 0) if task.info else 0
        })
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/set-cookies', methods=['POST'])
def set_cookies():
    """Сохранение cookies YouTube"""
    try:
        data = request.json
        if not data or 'cookies' not in data:
            return jsonify({'error': 'No cookies provided'}), 400
            
        session['youtube_cookies'] = data['cookies']
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error setting cookies: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/save_cookies', methods=['POST'])
def save_cookies():
    try:
        cookies = request.json
        
        # Сохраняем в config/youtube.cookies
        with open('config/youtube.cookies', 'w') as f:
            json.dump(cookies, f, indent=2)
            
        return jsonify({'status': 'success'})
    except Exception as e:
        app.logger.error(f"Failed to save cookies: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/static/<path:path>')
def send_static(path):
    """Отправка статических файлов"""
    try:
        return send_from_directory('static', path)
    except Exception as e:
        logger.error(f"Error sending static file: {e}")
        raise NotFound()

@app.route("/health")
def health_check():
    """Эндпоинт для проверки работоспособности сервера"""
    try:
        # Проверяем Redis
        redis_client.ping()
        
        # Проверяем доступность директорий
        for directory in [VIDEO_DIR, OUTPUT_DIR, TEMP_DIR]:
            if not os.path.exists(directory):
                raise RuntimeError(f"Directory not found: {directory}")
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "redis": "connected",
            "disk_space": psutil.disk_usage('/').free // (1024*1024)
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.errorhandler(NotFound)
def handle_not_found(e):
    """Обработка 404 ошибки"""
    if request.path.startswith('/static/'):
        return f"Static file {request.path} not found", 404
    return render_template('index.html'), 404

def cleanup_temp(temp_dir):
    """Очистка временной директории"""
    try:
        if os.path.exists(temp_dir):
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                try:
                    if os.path.isfile(item_path):
                        os.unlink(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except Exception as e:
                    logger.error(f"Error removing {item_path}: {e}")
        logger.info(f"Temporary directory {temp_dir} cleaned")
    except Exception as e:
        logger.error(f"Error cleaning temp directory: {e}")

def cleanup_old_files():
    """Очистка старых файлов"""
    try:
        # Очистка временных файлов
        temp_lifetime = app.config['storage']['temp_lifetime']
        temp_dir = app.config['storage']['temp_dir']
        
        current_time = time.time()
        for file in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, file)
            if os.path.getctime(file_path) + temp_lifetime < current_time:
                os.remove(file_path)
                
        # Очистка кэша если превышен лимит
        cache_size = app.config['storage']['cache_size_mb'] * 1024 * 1024
        cache_dir = app.config['storage']['cache_dir']
        
        total_size = sum(os.path.getsize(f) for f in os.listdir(cache_dir))
        if total_size > cache_size:
            files = sorted(os.listdir(cache_dir), 
                         key=lambda x: os.path.getctime(os.path.join(cache_dir, x)))
            while total_size > cache_size and files:
                os.remove(os.path.join(cache_dir, files.pop(0)))
                
    except Exception as e:
        app.logger.error(f"Error in cleanup: {e}")

# Запускаем очистку каждый час
scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_old_files, 'interval', hours=1)
scheduler.start()

@app.before_request
def before_request():
    request.start_time = time.time()

@app.after_request
def after_request(response):
    request_latency = time.time() - request.start_time
    REQUEST_COUNT.labels(request.method, request.endpoint, response.status_code).inc()
    REQUEST_LATENCY.observe(request_latency)
    return response

# Запуск сервера метрик Prometheus
start_http_server(9090)

if __name__ == "__main__":
    app.run(
        host=config['server'].get('host', '0.0.0.0'),
        port=config['server'].get('port', 8080)
    )
