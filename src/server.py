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
        required_params = ['temp_dir', 'memory', 'server']
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
            }
        }

# Инициализация конфигурации
config = load_config()

# Инициализация Flask
app = Flask(__name__, 
    static_folder='static',
    template_folder='templates'
)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev')

# Создание необходимых директорий
for directory in [VIDEO_DIR, OUTPUT_DIR, TEMP_DIR]:
    os.makedirs(directory, exist_ok=True)

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
    """Очистка старых временных файлов"""
    while True:
        try:
            for dir_path in [VIDEO_DIR, OUTPUT_DIR]:
                if not os.path.exists(dir_path):
                    continue
                    
                for file in os.listdir(dir_path):
                    try:
                        file_path = os.path.join(dir_path, file)
                        if time.time() - os.path.getmtime(file_path) > 24*60*60:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                    except Exception as e:
                        logger.error(f"Error removing old file {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error in cleanup_old_files: {e}")
        time.sleep(config['memory'].get('cleanup_interval', 3600))

def monitor_resources():
    """Мониторинг ресурсов сервера"""
    while True:
        try:
            # Проверка памяти
            memory = psutil.virtual_memory()
            if memory.percent > config['memory']['emergency_cleanup_threshold']:
                logger.warning(f"Memory usage critical: {memory.percent}%")
                cleanup_temp(config['temp_dir'])
                
            # Проверка диска
            disk = psutil.disk_usage('/')
            if disk.percent > 90:
                logger.warning(f"Disk usage critical: {disk.percent}%")
                cleanup_temp(config['temp_dir'])
                
        except Exception as e:
            logger.error(f"Error in monitor_resources: {e}")
        time.sleep(60)

# Запуск фоновых задач
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
monitor_thread.start()

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
