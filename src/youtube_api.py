import os
import logging
import requests
import json
import re
from pathlib import Path
from googleapiclient.discovery import build
import redis
import yt_dlp
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import subprocess

class YouTubeAPI:
    def __init__(self):
        """Инициализация YouTube API"""
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config()
        self._setup_session()
        self._setup_redis()
        self._setup_api()
        self.cookies = self._load_cookies()
        
    def _setup_session(self):
        """Настройка HTTP сессии с retry"""
        self.session = requests.Session()
        
        # Настройка retry стратегии
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
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
        """Установка куков сессии"""
        try:
            self.logger.info(f"Setting session cookies: {len(cookies)} cookies received")
            
            # Сохраняем куки в атрибут класса
            self.cookies = cookies
            
            # Создаем файл в формате Netscape
            netscape_cookie_file = '/app/config/youtube_netscape.cookies'
            with open(netscape_cookie_file, 'w') as nf:
                # Добавляем заголовок Netscape
                nf.write("# Netscape HTTP Cookie File\n")
                nf.write("# https://curl.se/docs/http-cookies.html\n")
                nf.write("# This file was generated by yt-dlp. Edit at your own risk.\n\n")
                
                # Добавляем куки
                if isinstance(cookies, list):
                    for cookie in cookies:
                        if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                            domain = cookie.get('domain', '.youtube.com')
                            path = cookie.get('path', '/')
                            secure = 'TRUE' if cookie.get('secure', True) else 'FALSE'
                            expiry = cookie.get('expiry', 0)
                            nf.write(f"{domain}\tTRUE\t{path}\t{secure}\t{expiry}\t{cookie['name']}\t{cookie['value']}\n")
                elif isinstance(cookies, dict):
                    for name, value in cookies.items():
                        nf.write(f".youtube.com\tTRUE\t/\tTRUE\t0\t{name}\t{value}\n")
            
            self.logger.info(f"Saved cookies to Netscape format at {netscape_cookie_file}")
            return True
        except Exception as e:
            self.logger.error(f"Error setting session cookies: {e}", exc_info=True)
            return False

    def download_video(self, url, output_path):
        """Скачивание видео с YouTube"""
        try:
            self.logger.info(f"Downloading video from URL: {url}")
            
            # Создаем директорию для выходного файла, если она не существует
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Пробуем скачать с помощью yt-dlp напрямую
            self.logger.info("Trying to download directly with yt-dlp")
            
            # Базовые опции yt-dlp
            ydl_opts = {
                'format': 'best[ext=mp4]/best',
                'outtmpl': output_path,
                'noplaylist': True,
                'verbose': True,
                'geo_bypass': True,
                'cookiefile': '/app/config/youtube_netscape.cookies',
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
                'referer': 'https://www.youtube.com/',
                'http_headers': {
                    'Accept-Language': 'en-US,en;q=0.9',
                },
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web', 'tv', 'ios'],
                    }
                }
            }
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                    
                # Проверяем, что файл был скачан
                if not os.path.exists(output_path):
                    raise FileNotFoundError(f"Video file not found at {output_path}")
                    
                self.logger.info(f"Video downloaded successfully to {output_path}")
                return output_path
            except Exception as e:
                self.logger.error(f"yt-dlp error: {e}")
                self.logger.info("Trying alternative download method")
                
                # Альтернативный метод с использованием --cookies-from-browser
                self.logger.info(f"Trying alternative download method for {url}")
                
                # Создаем команду для yt-dlp
                cmd = [
                    'yt-dlp',
                    '--format', 'best[ext=mp4]/best',
                    '--output', output_path,
                    '--no-playlist',
                    '--verbose',
                    '--geo-bypass',
                    '--cookies-from-browser', 'chrome',  # Используем куки из Chrome
                    '--user-agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
                    '--referer', 'https://www.youtube.com/',
                    '--add-header', 'Accept-Language:en-US,en;q=0.9',
                    '--extractor-args', 'youtube:player_client=android,web,tv,ios'
                ]
                
                # Добавляем URL
                cmd.append(url)
                
                self.logger.info(f"Running command: {' '.join(cmd)}")
                
                # Запускаем процесс
                process = subprocess.run(cmd, capture_output=True, text=True)
                
                # Проверяем результат
                if process.returncode != 0:
                    self.logger.error(f"Alternative download failed: {process.stderr}")
                    
                    # Пробуем еще один метод - с использованием youtube-dl
                    self.logger.info(f"Trying youtube-dl as a last resort for {url}")
                    cmd = [
                        'youtube-dl',
                        '--format', 'best[ext=mp4]/best',
                        '--output', output_path,
                        '--no-playlist',
                        '--verbose',
                        '--geo-bypass',
                        '--cookies', '/app/config/youtube_netscape.cookies',
                        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
                        '--referer', 'https://www.youtube.com/',
                        '--add-header', 'Accept-Language:en-US,en;q=0.9',
                        url
                    ]
                    
                    self.logger.info(f"Running command: {' '.join(cmd)}")
                    process = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if process.returncode != 0:
                        self.logger.error(f"youtube-dl also failed: {process.stderr}")
                        raise Exception(f"Failed to download video: {process.stderr}")
                
                # Проверяем, что файл был скачан
                if not os.path.exists(output_path):
                    raise FileNotFoundError(f"Video file not found at {output_path}")
                
                self.logger.info(f"Video downloaded successfully to {output_path} using alternative method")
                return output_path
        except Exception as e:
            self.logger.error(f"Error downloading video: {e}")
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
            # Используем абсолютный путь к файлу
            cookie_file = '/app/config/youtube.cookies'
            self.logger.info(f"Loading cookies from: {cookie_file}")
            
            if os.path.exists(cookie_file):
                with open(cookie_file, 'r') as f:
                    cookies = json.load(f)
                    self.logger.info(f"Loaded {len(cookies)} cookies")
                    
                    # Создаем файл в формате Netscape
                    netscape_cookie_file = '/app/config/youtube_netscape.cookies'
                    with open(netscape_cookie_file, 'w') as nf:
                        # Добавляем заголовок Netscape
                        nf.write("# Netscape HTTP Cookie File\n")
                        nf.write("# https://curl.se/docs/http-cookies.html\n")
                        nf.write("# This file was generated by yt-dlp. Edit at your own risk.\n\n")
                        
                        # Добавляем куки
                        if isinstance(cookies, list):
                            for cookie in cookies:
                                if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                                    domain = cookie.get('domain', '.youtube.com')
                                    path = cookie.get('path', '/')
                                    secure = 'TRUE' if cookie.get('secure', True) else 'FALSE'
                                    expiry = cookie.get('expiry', 0)
                                    nf.write(f"{domain}\tTRUE\t{path}\t{secure}\t{expiry}\t{cookie['name']}\t{cookie['value']}\n")
                        elif isinstance(cookies, dict):
                            for name, value in cookies.items():
                                nf.write(f".youtube.com\tTRUE\t/\tTRUE\t0\t{name}\t{value}\n")
                    
                    self.logger.info(f"Converted cookies to Netscape format at {netscape_cookie_file}")
                    return cookies
            else:
                self.logger.warning("Cookie file not found")
                return None
        except Exception as e:
            self.logger.error(f"Error loading cookies: {e}", exc_info=True)
            return None

    def save_cookies_to_netscape_format(self):
        """Сохранение куков в формате Netscape для yt-dlp"""
        try:
            cookie_file = '/app/config/youtube.cookies'
            netscape_cookie_file = '/app/config/youtube_netscape.cookies'
            
            if not os.path.exists(cookie_file):
                self.logger.warning(f"Cookie file not found: {cookie_file}")
                return
            
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
            
            with open(netscape_cookie_file, 'w') as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# This file is generated by youtube-converter. Do not edit.\n\n")
                
                for cookie in cookies:
                    domain = cookie.get('domain', '.youtube.com')
                    flag = "TRUE"
                    path = cookie.get('path', '/')
                    secure = "TRUE"
                    expiry = "0"  # Не истекает
                    name = cookie.get('name', '')
                    value = cookie.get('value', '')
                    
                    if name and value:
                        f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
            
            self.logger.info(f"Saved cookies to Netscape format at {netscape_cookie_file}")
            return netscape_cookie_file
        except Exception as e:
            self.logger.error(f"Error saving cookies to Netscape format: {e}")
            return None