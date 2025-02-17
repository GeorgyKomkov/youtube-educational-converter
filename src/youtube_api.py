import os
import json
import logging
import redis
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import yt_dlp

class YouTubeAPI:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.youtube = None
        self.api_key = self._load_api_key()
        self.client_secrets = self._load_client_secrets()
        self.initialize_api()
        
        # Улучшенное подключение к Redis
        redis_url = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

    def _load_api_key(self):
        """Загрузка API ключа из файла"""
        try:
            api_key_path = os.path.join('config', 'api.txt')
            with open(api_key_path, 'r') as f:
                return f.read().strip()
        except Exception as e:
            self.logger.error(f"Error loading API key: {e}")
            raise

    def _load_client_secrets(self):
        """Загрузка client secrets из файла"""
        try:
            with open('client_secrets.json', 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading client secrets: {e}")
            raise

    def initialize_api(self):
        """Инициализация YouTube API"""
        try:
            self.youtube = build('youtube', 'v3', developerKey=self.api_key)
            self.logger.info("YouTube API initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing YouTube API: {e}")
            raise

    def get_video_info(self, video_id):
        try:
            cookies_path = os.path.join('config', 'youtube.cookies')
            if not os.path.exists(cookies_path):
                self.logger.error(f"Cookies file not found at {cookies_path}")
                return None, "Cookies file not found"

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'cookiefile': cookies_path
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                return info, None
        except Exception as e:
            self.logger.error(f"Error getting video info: {str(e)}")
            return None, str(e)

    def get_download_url(self, video_id):
        """Получает прямую ссылку на скачивание"""
        info, error = self.get_video_info(video_id)
        if error:
            return None, error
            
        # Возвращаем прямую ссылку на видео
        download_url = f"https://www.youtube.com/watch?v={video_id}"
        return download_url, info['title']
