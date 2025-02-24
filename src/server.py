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
import logging.config
from datetime import datetime
import time
from threading import Lock
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
import socket
from celery.result import AsyncResult

# Импортируем нужные модули
from .youtube_api import YouTubeAPI
from .process_video import VideoProcessor

def setup_logging():
    try:
        with open('/app/config/logging.yaml', 'r') as f:
            config = yaml.safe_load(f)
        logging.config.dictConfig(config)
    except Exception as e:
        print(f"Error setting up logging: {e}")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

setup_logging()
logger = logging.getLogger(__name__)

# Константы
VIDEO_DIR = "/app/videos"
OUTPUT_DIR = "/app/output"
TEMP_DIR = "/app/temp"

def load_config():
    """Загрузка и валидация конфигурации"""
    try:
        with open('/app/config/config.yaml', 'r') as f:
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
            'temp_dir': '/app/temp',
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
                'cache_dir': '/app/temp'
            }
        }

# Инициализация конфигурации
config = load_config()

# Инициализация Flask
app = Flask(__name__,
    static_folder='/app/static',
    template_folder='/app/templates'
)
app.config.update({
    'MAX_CONTENT_LENGTH': 100 * 1024 * 1024,  # уменьшаем до 100MB
    'UPLOAD_FOLDER': '/app/temp'
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
celery = Celery('tasks', 
    broker=redis_url,
    backend=redis_url  # Изменено с result_backend на backend
)

celery.conf.update({
    'broker_url': redis_url,
    'result_backend': redis_url,
    'task_track_started': True,
    'task_serializer': 'json',
    'result_serializer': 'json',
    'accept_content': ['json'],
    'worker_max_tasks_per_child': 1,
    'worker_max_memory_per_child': 256*1024,  # 256MB
    'task_time_limit': 1800,  # 30 минут
    'worker_concurrency': 1,
    'broker_connection_retry': True,
    'broker_connection_max_retries': 0,
    'result_expires': 3600,  # Результаты хранятся 1 час
})

# Инициализация Redis клиента
redis_client = redis.from_url(redis_url, decode_responses=True)

# После инициализации Redis клиента
try:
    redis_client.ping()
    logger.info("Successfully connected to Redis")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    sys.exit(1)

# Инициализация YouTube API
youtube_api = YouTubeAPI()

# Метрики
REQUEST_COUNT = Counter('request_count_total', 'Total request count', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('request_latency_seconds', 'Request latency in seconds')

# Блокировка для синхронизации
cleanup_lock = Lock()

@celery.task(bind=True, max_retries=3)
def process_video_task(self, video_url):
    try:
        logger.info(f"Starting video processing task for URL: {video_url}")
        processor = VideoProcessor(app.config)
        result = processor.process_video(video_url)
        logger.info(f"Video processing completed: {result}")
        return result
    except Exception as exc:
        logger.error(f"Error processing video: {exc}")
        raise self.retry(exc=exc, countdown=60)

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

@app.route('/process_video', methods=['POST'])
def process_video():
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400
            
        url = data.get('url')
        task = process_video_task.delay(url)
        
        return jsonify({
            'task_id': task.id,
            'status': 'processing'
        })
    except Exception as e:
        logger.error(f"Error processing video request: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/status/<task_id>')
def get_task_status(task_id):
    try:
        # Получаем задачу по ID
        task = AsyncResult(task_id)
        logger.info(f"Checking status for task {task_id}: {task.status}")
        
        if task.state == 'PENDING':
            response = {
                'status': 'processing',
                'progress': 0
            }
        elif task.state == 'SUCCESS':
            response = {
                'status': 'completed',
                'progress': 100,
                'result': task.result
            }
        elif task.state == 'FAILURE':
            logger.error(f"Task {task_id} failed: {task.result}")
            response = {
                'status': 'failed',
                'error': str(task.result)
            }
        else:
            response = {
                'status': 'processing',
                'progress': task.info.get('progress', 0) if task.info else 0
            }
            
        logger.info(f"Status response for task {task_id}: {response}")
        return jsonify(response)
        
    except Exception as e:
        logger.exception(f"Error checking task status: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

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
    # Проверяем, не занят ли порт
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 9091))
    if result != 0:  # Порт свободен
        start_http_server(9091)
    sock.close()
except Exception as e:
    logger.error(f"Failed to start Prometheus server: {e}")

if __name__ == "__main__":
    app.run(
        host=config['server'].get('host', '0.0.0.0'),
        port=config['server'].get('port', 8080)
    )
