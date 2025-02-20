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
from .youtube_api import YouTubeAPI
from .process_video import VideoProcessor

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
app.config.update({
    'MAX_CONTENT_LENGTH': 500 * 1024 * 1024,  # 500MB max-size
    'UPLOAD_FOLDER': 'temp'
})

# Добавить проверку существования директорий при старте
for directory in [VIDEO_DIR, OUTPUT_DIR, TEMP_DIR]:
    try:
        os.makedirs(directory, exist_ok=True)
        os.chmod(directory, 0o777)
    except Exception as e:
        logger.error(f"Failed to create directory {directory}: {e}")
        sys.exit(1)

# Конфигурация Celery
redis_url = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
celery = Celery('tasks', broker=redis_url)
redis_client = redis.from_url(redis_url, decode_responses=True)

# Инициализация YouTube API
youtube_api = YouTubeAPI()

# Метрики
REQUEST_COUNT = Counter('request_count_total', 'Total request count', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('request_latency_seconds', 'Request latency in seconds')

# Блокировка для синхронизации
cleanup_lock = threading.Lock()

# Ограничение количества одновременных задач
celery.conf.update(
    worker_max_tasks_per_child=1,
    worker_max_memory_per_child=512*1024,  # 512MB
    task_time_limit=3600,  # 1 час
    worker_concurrency=1  # только 1 процесс
)

@celery.task(bind=True, max_retries=3)
def process_video_task(self, video_url):
    try:
        processor = VideoProcessor(app.config)
        return processor.process_video(video_url)
    except Exception as exc:
        logger.error(f"Error processing video: {exc}")
        self.retry(exc=exc, countdown=60)

def check_disk_space():
    """Проверка и очистка диска при необходимости"""
    with cleanup_lock:
        try:
            for path in [app.config['temp_dir'], app.config['output_dir']]:
                usage = psutil.disk_usage(path)
                if usage.percent > app.config['storage']['emergency_cleanup_threshold']:
                    cleanup_old_files(path)
        except Exception as e:
            logger.error(f"Error in disk space check: {e}")

def cleanup_old_files(directory):
    """Очистка старых файлов"""
    try:
        current_time = time.time()
        max_age = app.config['storage']['max_file_age']
        
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.getctime(file_path) + max_age < current_time:
                    try:
                        os.remove(file_path)
                        logger.info(f"Removed old file: {file_path}")
                    except Exception as e:
                        logger.error(f"Error removing file {file_path}: {e}")
    except Exception as e:
        logger.error(f"Error in cleanup: {e}")

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

        # Создаем задачу
        task = process_video_task.delay(data['url'])
        
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

@app.before_request
def before_request():
    request.start_time = time.time()
    # Проверка доступной памяти
    if psutil.virtual_memory().available < 200 * 1024 * 1024:  # 200MB
        return 'Server is busy, try later', 503

@app.after_request
def after_request(response):
    try:
        request_latency = time.time() - request.start_time
        REQUEST_COUNT.labels(
            request.method, 
            request.endpoint, 
            response.status_code
        ).inc()
        REQUEST_LATENCY.observe(request_latency)
    except Exception as e:
        logger.error(f"Error recording metrics: {e}")
    return response

# Запуск планировщика очистки
scheduler = BackgroundScheduler()
scheduler.add_job(check_disk_space, 'interval', hours=1)
scheduler.start()

# Запуск сервера метрик Prometheus
try:
    start_http_server(9090)
except Exception as e:
    logger.error(f"Failed to start Prometheus server: {e}")

if __name__ == "__main__":
    app.run(
        host=config['server'].get('host', '0.0.0.0'),
        port=config['server'].get('port', 8080)
    )
