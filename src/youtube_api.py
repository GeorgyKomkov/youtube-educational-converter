import os
import logging.config
import redis
from googleapiclient.discovery import build
import yt_dlp
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import re

class YouTubeAPI:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config()
        self._setup_http_session()
        self._setup_redis()
        self._setup_api()
        self.cookies = None
        
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
            
            self.api_key = api_key  # Сохраняем API ключ
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
        self.logger.info("Session cookies set successfully")

    def download_video(self, url, output_path):
        """Загрузка видео с использованием yt-dlp"""
        try:
            # Проверяем видео через API
            video_id = self._extract_video_id(url)
            if not video_id:
                raise ValueError("Invalid YouTube URL")

            # Проверяем доступность видео через API
            try:
                video_info = self.youtube.videos().list(
                    part='snippet,contentDetails',
                    id=video_id
                ).execute()
                
                if not video_info.get('items'):
                    raise ValueError("Video not found or not accessible")
                    
            except Exception as e:
                self.logger.error(f"Failed to get video info from API: {e}")
                raise

            # Настройки для yt-dlp
            ydl_opts = {
                'format': 'best[height<=480]',
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False
            }

            # Добавляем куки, если они есть
            if self.cookies:
                ydl_opts['cookies'] = self.cookies
                self.logger.info("Using session cookies for download")
            
            # Скачиваем видео
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                self.logger.info(f"Video downloaded successfully: {url}")
                
        except Exception as e:
            self.logger.error(f"Failed to download video: {e}")
            raise

    def _extract_video_id(self, url):
        """Извлечение ID видео из URL"""
        try:
            # Поддержка различных форматов URL YouTube
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
            if self.youtube:
                self.youtube.close()
            if self.session:
                self.session.close()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def _load_api_key(self):
        """Загрузка API ключа"""
        return os.environ.get('YOUTUBE_API_KEY')

    def _load_config(self):
        """Загрузка конфигурации"""
        try:
            with open('config/config.yaml', 'r') as f:
                import yaml
                config = yaml.safe_load(f)
                return config.get('youtube_api', {})
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {}
