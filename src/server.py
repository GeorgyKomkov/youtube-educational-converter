from flask import (
    Flask, 
    request, 
    jsonify, 
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
from flask_cors import CORS
import requests
import subprocess

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

@celery.task(bind=True)
def process_video_task(self, url):
    """Задача для обработки видео"""
    try:
        logger.info(f"Starting video processing task for URL: {url}")
        
        # Проверяем наличие куки, но не выбрасываем ошибку, если их нет
        cookie_file = '/app/config/youtube.cookies'
        if os.path.exists(cookie_file):
            logger.info("YouTube cookies found, using them for download")
        else:
            logger.warning("No YouTube cookies found, download may be limited")
            
        # Проверяем наличие youtube-dl и yt-dlp
        try:
            subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
            logger.info("yt-dlp is available")
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.error("yt-dlp is not available!")
            
        try:
            subprocess.run(['youtube-dl', '--version'], capture_output=True, check=True)
            logger.info("youtube-dl is available")
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.error("youtube-dl is not available!")
            
        # Инициализация VideoProcessor
        processor = VideoProcessor(config)
        
        # Обработка видео
        result = processor.process_video(url)
        logger.info(f"Video processing completed: {result}")
        return result
            
    except Exception as e:
        logger.exception(f"Task failed with error: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }

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
    """Обработка запроса на конвертацию видео"""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            logger.error("No URL in request data")
            return jsonify({'error': 'No URL provided'}), 400
            
        url = data.get('url')
        logger.info(f"Received video processing request for URL: {url}")
        
        # Запускаем задачу, передавая куки как параметр
        task = process_video_task.delay(url=url)
        logger.info(f"Task created with ID: {task.id}")
        
        return jsonify({
            'task_id': task.id,
            'status': 'processing'
        })
            
    except Exception as e:
        logger.exception(f"Error processing request: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/status/<task_id>')
def get_task_status(task_id):
    try:
        # Получаем задачу по ID
        task = AsyncResult(task_id, app=celery)
        logger.info(f"Checking status for task {task_id}: {task.state}")
        
        response = {
            'status': 'processing',
            'progress': 0
        }

        if task.state == 'PENDING':
            response = {
                'status': 'processing',
                'progress': 0
            }
        elif task.state == 'SUCCESS':
            result = task.get()  # Получаем результат задачи
            response = {
                'status': 'completed',
                'progress': 100,
                'result': result
            }
        elif task.state == 'FAILURE':
            response = {
                'status': 'failed',
                'error': str(task.result),  # Получаем информацию об ошибке
                'progress': 0
            }
        elif task.state == 'PROGRESS':
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

@app.route('/api/save-cookies', methods=['POST', 'OPTIONS'])
def save_cookies():
    """Сохранение куки YouTube в файл"""
    logger.info("=== Starting save-cookies request ===")

    if request.method == 'OPTIONS':
        response = app.make_default_options_response()
        return response

    try:
        data = request.get_json()
        logger.info(f"Received cookies request data: {data is not None}")

        if not data or 'cookies' not in data:
            logger.error("No cookies in request data")
            return jsonify({'error': 'No cookies provided'}), 400

        cookies = data.get('cookies')
        logger.info(f"Number of cookies received: {len(cookies)}")

        # Создаем директорию config если её нет
        config_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config')
        os.makedirs(config_dir, exist_ok=True)
        logger.info(f"Config directory created/verified: {config_dir}")

        # Устанавливаем права на директорию
        os.chmod(config_dir, 0o755)

        cookie_file = os.path.join(config_dir, 'youtube.cookies')
        logger.info(f"Saving cookies to: {cookie_file}")

        # Сохраняем куки в файл
        with open(cookie_file, 'w') as f:
            json.dump(cookies, f, indent=2)
            logger.info("Cookies successfully saved to file")

        # Проверяем, что файл создан и содержит данные
        if os.path.exists(cookie_file):
            file_size = os.path.getsize(cookie_file)
            logger.info(f"Cookie file created successfully. Size: {file_size} bytes")
        else:
            raise FileNotFoundError("Cookie file was not created")

        # Передаем куки в YouTubeAPI
        youtube_api = YouTubeAPI()
        youtube_api.set_session_cookies(cookies)
        logger.info("Cookies passed to YouTubeAPI")

        return jsonify({
            'success': True,
            'message': 'Cookies saved successfully',
            'file': cookie_file
        })

    except Exception as e:
        logger.error(f"Error in save-cookies: {str(e)}", exc_info=True)
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
    logger.error(f"Failed to starts Prometheus server: {e}")

@app.route('/api/check-auth')
def check_auth():
    """Проверка авторизации YouTube"""
    try:
        # Проверяем наличие файла с куки
        cookie_file = os.path.join('config', 'youtube.cookies')
        if not os.path.exists(cookie_file):
            return jsonify({'authorized': False, 'error': 'No cookies found'})
            
        # Проверяем валидность куки
        with open(cookie_file, 'r') as f:
            cookies = json.load(f)
            
        # Проверяем наличие необходимых куки
        required_cookies = ['CONSENT', 'VISITOR_INFO1_LIVE', 'LOGIN_INFO']
        has_all_cookies = all(
            any(cookie['name'] == req for cookie in cookies)
            for req in required_cookies
        )
        
        return jsonify({'authorized': has_all_cookies})
        
    except Exception as e:
        logger.error(f"Error checking auth: {e}")
        return jsonify({'authorized': False, 'error': str(e)})

@app.route('/get-youtube-cookies', methods=['GET'])
def get_youtube_cookies():
    """Получение куков YouTube через серверный запрос"""
    try:
        logger.info("Fetching YouTube cookies")
        
        # Создаем сессию с заголовками как у обычного браузера
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Referer': 'https://www.google.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Делаем запрос к YouTube
        response = session.get('https://www.youtube.com/')
        
        if response.status_code != 200:
            logger.error(f"Failed to fetch YouTube page: {response.status_code}")
            return jsonify({'status': 'error', 'error': f"Failed to fetch YouTube page: {response.status_code}"})
        
        # Получаем куки
        cookies = [{'name': c.name, 'value': c.value, 'domain': c.domain, 'path': c.path} for c in session.cookies]
        logger.info(f"Got {len(cookies)} cookies from YouTube")
        
        # Добавляем дополнительные куки, которые могут быть полезны
        additional_cookies = [
            {'name': 'CONSENT', 'value': 'YES+cb', 'domain': '.youtube.com', 'path': '/'},
            {'name': 'VISITOR_INFO1_LIVE', 'value': 'y9-h6iLPDEY', 'domain': '.youtube.com', 'path': '/'},
            {'name': 'YSC', 'value': 'DwKYMZ-9Ky4', 'domain': '.youtube.com', 'path': '/'},
            {'name': 'PREF', 'value': 'f4=4000000&tz=Europe%2FMoscow', 'domain': '.youtube.com', 'path': '/'},
            {'name': 'GPS', 'value': '1', 'domain': '.youtube.com', 'path': '/'},
            {'name': 'SIDCC', 'value': 'ACA-OxPm6CjH5mxlwGnUQeUo9ZLgE7RYIiZV8LtVnqR3qdWzs5U', 'domain': '.youtube.com', 'path': '/'},
            {'name': '__Secure-1PSIDCC', 'value': 'ACA-OxOxDLmYDz9mHUZQeUo9ZLgE7RYIiZV8LtVnqR3qdWzs5U', 'domain': '.youtube.com', 'path': '/'},
            {'name': '__Secure-3PSIDCC', 'value': 'ACA-OxPCLmYDz9mHUZQeUo9ZLgE7RYIiZV8LtVnqR3qdWzs5U', 'domain': '.youtube.com', 'path': '/'},
        ]
        
        # Добавляем дополнительные куки, если их еще нет
        for additional_cookie in additional_cookies:
            if not any(c.get('name') == additional_cookie['name'] for c in cookies):
                cookies.append(additional_cookie)
        
        # Сохраняем куки в JSON формате
        with open('/app/config/youtube.cookies', 'w') as f:
            json.dump(cookies, f)
        
        # Сохраняем куки в формате Netscape
        with open('/app/config/youtube_netscape.cookies', 'w') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# https://curl.se/docs/http-cookies.html\n")
            f.write("# This file was generated by yt-dlp\n\n")
            
            for cookie in cookies:
                domain = cookie.get('domain', '.youtube.com')
                if not domain.startswith('.'):
                    domain = '.' + domain
                
                path = cookie.get('path', '/')
                secure = 'TRUE'
                expires = '0'  # Session cookie
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                
                f.write(f"{domain}\tTRUE\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")
        
        logger.info("Cookies saved in both JSON and Netscape formats")
        
        # Пробуем создать файл куков с помощью yt-dlp
        try:
            logger.info("Trying to create cookies file with yt-dlp")
            cmd = [
                'yt-dlp',
                '--cookies-from-browser', 'chrome',
                '--cookies', '/app/config/youtube_browser.cookies'
            ]
            
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode == 0:
                logger.info("Successfully created cookies file from browser")
            else:
                logger.warning(f"Failed to create cookies file from browser: {process.stderr}")
        except Exception as e:
            logger.warning(f"Error creating cookies file from browser: {e}")
        
        return jsonify({
            'status': 'success',
            'message': f"Successfully fetched {len(cookies)} cookies from YouTube"
        })
    except Exception as e:
        logger.error(f"Error getting YouTube cookies: {e}")
        return jsonify({'status': 'error', 'error': str(e)})

def check_youtube_auth(cookies_list):
    """Проверка валидности куков YouTube"""
    try:
        session = requests.Session()
        
        # Преобразуем список куков в словарь для сессии
        for cookie in cookies_list:
            session.cookies.set(
                cookie['name'], 
                cookie['value'], 
                domain=cookie.get('domain', '.youtube.com'),
                path=cookie.get('path', '/')
            )
            
        # Пробуем получить данные профиля
        response = session.get('https://www.youtube.com/feed/subscriptions')
        
        # Если нет редиректа на логин, значит куки валидные
        return 'signin' not in response.url
        
    except Exception as e:
        logger.error(f"Error checking YouTube auth: {e}")
        return False

# Правильная настройка CORS для всего приложения
CORS(app, supports_credentials=True, origins=[
    "http://localhost:8080",
    "http://localhost:5000",
    "http://127.0.0.1:8080",
    "https://your-production-domain.com"
], methods=["GET", "POST", "OPTIONS"])

@app.route('/set-cookies', methods=['POST'])
def set_cookies():
    """API для установки куков YouTube"""
    try:
        data = request.json
        if not data or 'cookies' not in data:
            return jsonify({'error': 'Cookies are required'}), 400
            
        cookies = data['cookies']
        
        # Сохраняем куки в файл
        cookie_file = '/app/config/youtube.cookies'
        with open(cookie_file, 'w') as f:
            json.dump(cookies, f)
            
        # Инициализируем YouTube API и устанавливаем куки
        youtube_api = YouTubeAPI()
        youtube_api.set_session_cookies(cookies)
        
        return jsonify({'status': 'success', 'message': f'Saved {len(cookies)} cookies'})
        
    except Exception as e:
        logger.error(f"Error setting cookies: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/youtube-proxy', methods=['GET'])
def youtube_proxy():
    """Прокси для запросов к YouTube"""
    try:
        url = request.args.get('url', 'https://www.youtube.com/')
        
        # Создаем сессию с куками пользователя
        session = requests.Session()
        
        # Копируем заголовки из запроса пользователя
        headers = {
            'User-Agent': request.headers.get('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.youtube.com/',
            'Origin': 'https://www.youtube.com',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'TE': 'trailers'
        }
        
        # Копируем куки из запроса пользователя
        for cookie_name, cookie_value in request.cookies.items():
            session.cookies.set(cookie_name, cookie_value)
        
        # Делаем запрос к YouTube
        response = session.get(url, headers=headers)
        
        # Получаем куки из ответа и сохраняем их
        cookies = []
        for cookie in session.cookies:
            cookie_dict = {
                'name': cookie.name,
                'value': cookie.value,
                'domain': cookie.domain,
                'path': cookie.path
            }
            cookies.append(cookie_dict)
        
        # Добавляем дополнительные куки для обхода защиты от ботов
        additional_cookies = [
            {'name': 'CONSENT', 'value': 'YES+cb', 'domain': '.youtube.com', 'path': '/'},
            {'name': 'VISITOR_INFO1_LIVE', 'value': 'y-NbKGnXEZw', 'domain': '.youtube.com', 'path': '/'},
            {'name': 'GPS', 'value': '1', 'domain': '.youtube.com', 'path': '/'},
            {'name': 'YSC', 'value': 'DwKYMZ-9Ky4', 'domain': '.youtube.com', 'path': '/'},
            {'name': 'PREF', 'value': 'f4=4000000&tz=Europe%2FMoscow', 'domain': '.youtube.com', 'path': '/'},
            {'name': 'LOGIN_INFO', 'value': 'AFmmF2swRQIhAP5uKrlfFRJ_XmEwZeJzGda3ZCNR9tiXV9mMr5jMCQZBAiAw3WPHy-dEOeHrJL0nVTI1CzHYmQIBKQAQDhkwuDQpMw:QUQ3MjNmeXJnUmRiNGVHMHBJdGxCNV9QMFBrNWNTVnVLUWFLN0xQTHNkWUJfSHJqWUFKSXVDVmNlVXBITXRhNGFKSHlKVTJxUWNfVFJVWnJKSXZMVnVxdVZyTGFKRnJIZVBxZWJLdVVkRGJzRnJvWGJXdVBfVnVLUWFLN0xQTHNkWUJfSHJqWUFKSXVDVmNlVXBITXRhNGFKSHlKVTJxUWNfVFJVWnJKSXZMVnVxdVZyTGFKRnJIZVBxZWJLdVVkRGJzRnJvWGJXdVA=', 'domain': '.youtube.com', 'path': '/'}
        ]
        
        # Добавляем дополнительные куки, если их еще нет
        for additional_cookie in additional_cookies:
            if not any(c.get('name') == additional_cookie['name'] for c in cookies):
                cookies.append(additional_cookie)
        
        # Сохраняем куки в файл
        if cookies:
            with open('/app/config/youtube.cookies', 'w') as f:
                json.dump(cookies, f)
            
            # Инициализируем YouTube API и устанавливаем куки
            youtube_api = YouTubeAPI()
            youtube_api.set_session_cookies(cookies)
            
            logger.info(f"Saved {len(cookies)} YouTube cookies via proxy")
        
        # Возвращаем ответ от YouTube
        return response.content, response.status_code, response.headers.items()
    except Exception as e:
        logger.error(f"Error in YouTube proxy: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Скачивание обработанного файла"""
    try:
        logger.info(f"Download request for file: {filename}")
        
        # Ищем файл в директориях
        for directory in [TEMP_DIR, OUTPUT_DIR]:
            # Ищем файл в корне директории
            file_path = os.path.join(directory, filename)
            if os.path.exists(file_path):
                logger.info(f"File found at {file_path}")
                return send_from_directory(directory, filename, as_attachment=True)
                
            # Ищем файл в поддиректориях
            for root, dirs, files in os.walk(directory):
                if filename in files:
                    file_path = os.path.join(root, filename)
                    logger.info(f"File found at {file_path}")
                    return send_from_directory(root, filename, as_attachment=True)
        
        logger.error(f"File not found: {filename}")
        return jsonify({'error': 'File not found'}), 404
        
    except Exception as e:
        logger.exception(f"Error downloading file: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(
        host=config['server'].get('host', '0.0.0.0'),
        port=config['server'].get('port', 8080)
    )
