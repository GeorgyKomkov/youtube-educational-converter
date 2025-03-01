import os
import logging.config
import redis
from googleapiclient.discovery import build
import yt_dlp
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import re
import json
from pathlib import Path

class YouTubeAPI:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config()
        self._setup_http_session()
        self._setup_redis()
        self._setup_api()
        self.cookies = self._load_cookies()  # Загружаем куки при инициализации
        
    def _setup_http_session(self):
        """Настройка HTTP сессии с retry и timeout"""
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
    def _setup_redis(self):
        """Настройка подключения к Redis"""
        try:
            redis_url = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=5
            )
            self.redis_client.ping()
        except Exception as e:
            self.logger.error(f"Redis connection failed: {e}")
            self.redis_client = None
            
    def _setup_api(self):
        """Настройка YouTube API"""
        try:
            api_key = self._load_api_key()
            if not api_key:
                raise ValueError("YouTube API key not found")
            
            self.api_key = api_key
            self.youtube = build(
                'youtube', 
                'v3', 
                developerKey=api_key,
                cache_discovery=False
            )
            self.logger.info("YouTube API initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize YouTube API: {e}")
            raise

    def get_video_info(self, video_id, timeout=(5, 30)):
        """Получение информации о видео с таймаутом"""
        try:
            response = self.session.get(
                f"https://www.googleapis.com/youtube/v3/videos",
                params={
                    'id': video_id,
                    'part': 'snippet,contentDetails',
                    'key': self.api_key
                },
                timeout=timeout
            )
            response.raise_for_status()
            
            data = response.json()
            if not data.get('items'):
                raise ValueError("Video not found")
                
            return data['items'][0]
            
        except requests.Timeout:
            self.logger.error(f"Timeout getting video info for {video_id}")
            raise
        except Exception as e:
            self.logger.error(f"Error getting video info: {e}")
            raise

    def set_session_cookies(self, cookies):
        """Установка куки из сессии"""
        if not cookies:
            self.logger.warning("No cookies provided in session")
            return
        self.cookies = cookies
        
        # Сохраняем куки в файл для использования в yt-dlp
        try:
            cookie_path = Path('config/youtube.cookies')
            with open(cookie_path, 'w') as f:
                json.dump(cookies, f)
            self.logger.info("Session cookies saved to file successfully")
        except Exception as e:
            self.logger.error(f"Failed to save cookies to file: {e}")

    def download_video(self, url, output_path):
        """Загрузка видео с использованием yt-dlp"""
        try:
            # Проверяем видео через API
            video_id = self._extract_video_id(url)
            if not video_id:
                raise ValueError("Invalid YouTube URL")

            # Загружаем куки
            cookies = self._load_cookies()
            self.logger.info(f"Using {len(cookies) if cookies else 0} cookies for download")

            # Создаем временный файл с куками в формате Netscape
            cookie_jar = None
            if cookies:
                try:
                    import tempfile
                    cookie_jar = tempfile.NamedTemporaryFile(delete=False, suffix='.txt')
                    
                    # Записываем куки в формате Netscape
                    with open(cookie_jar.name, 'w') as f:
                        f.write("# Netscape HTTP Cookie File\n")
                        for cookie in cookies:
                            domain = cookie.get('domain', '.youtube.com')
                            flag = "TRUE"
                            path = cookie.get('path', '/')
                            secure = "TRUE" if 'Secure' in cookie.get('name', '') else "FALSE"
                            expiry = "0"  # Сессионная кука
                            name = cookie.get('name', '')
                            value = cookie.get('value', '')
                            
                            f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
                            
                    self.logger.info(f"Created cookie jar at {cookie_jar.name}")
                except Exception as e:
                    self.logger.error(f"Failed to create cookie jar: {e}")
                    if cookie_jar:
                        try:
                            os.unlink(cookie_jar.name)
                        except:
                            pass
                    cookie_jar = None

            # Настройки для yt-dlp
            ydl_opts = {
                'format': 'best',
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
                'cookiefile': cookie_jar.name if cookie_jar else None,
                'nocheckcertificate': True
            }
            
            # Скачиваем видео
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self.logger.info(f"Starting download of {url}")
                ydl.download([url])
                self.logger.info(f"Video downloaded successfully: {url}")
                
            # Удаляем временный файл с куками
            if cookie_jar:
                try:
                    os.unlink(cookie_jar.name)
                    self.logger.info(f"Removed temporary cookie jar")
                except Exception as e:
                    self.logger.error(f"Failed to remove cookie jar: {e}")
                
        except Exception as e:
            self.logger.error(f"Failed to download video: {e}", exc_info=True)
            raise

    def _extract_video_id(self, url):
        """Извлечение ID видео из URL"""
        try:
            patterns = [
                r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
                r'youtu\.be\/([0-9A-Za-z_-]{11})',
                r'youtube\.com\/embed\/([0-9A-Za-z_-]{11})'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to extract video ID: {e}")
            return None

    def cleanup(self):
        """Очистка ресурсов"""
        try:
            if hasattr(self, 'youtube'):
                self.youtube.close()
            if hasattr(self, 'session'):
                self.session.close()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def _load_api_key(self):
        """Загрузка API ключа"""
        return os.environ.get('YOUTUBE_API_KEY')

    def _load_config(self):
        """Загрузка конфигурации"""
        try:
            config_path = Path('config/config.yaml')
            if not config_path.exists():
                return {}
                
            with open(config_path, 'r') as f:
                import yaml
                config = yaml.safe_load(f)
                return config.get('youtube_api', {})
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {}

    def _load_cookies(self):
        """Загрузка cookies из файла"""
        try:
            # Используем тот же путь, что и при сохранении
            cookie_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'youtube.cookies')
            self.logger.info(f"Loading cookies from: {cookie_file}")
            
            if os.path.exists(cookie_file):
                with open(cookie_file, 'r') as f:
                    cookies = json.load(f)
                    self.logger.info(f"Loaded {len(cookies)} cookies")
                    
                    # Проверяем формат куков
                    if isinstance(cookies, list) and len(cookies) > 0 and 'name' in cookies[0]:
                        # Куки в формате списка объектов
                        self.logger.info(f"Cookie format: list of objects")
                        return cookies
                    elif isinstance(cookies, dict):
                        # Куки в формате словаря
                        self.logger.info(f"Cookie format: dictionary")
                        formatted_cookies = []
                        for name, value in cookies.items():
                            formatted_cookies.append({
                                'name': name,
                                'value': value,
                                'domain': '.youtube.com',
                                'path': '/'
                            })
                        return formatted_cookies
                    else:
                        self.logger.warning(f"Unknown cookie format: {type(cookies)}")
                        return None
            else:
                self.logger.warning("Cookie file not found")
                return None
        except Exception as e:
            self.logger.error(f"Error loading cookies: {e}", exc_info=True)
            return None
