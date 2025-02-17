import os
import json
import logging
import redis
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import yt_dlp
import yaml

class YouTubeAPI:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.youtube = None
        self.config = self._load_config()
        self.api_key = self._load_api_key()
        self.client_secrets = self._load_client_secrets()
        self.initialize_api()
        
        # Улучшенное подключение к Redis
        redis_url = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        
        # Создание временной директории
        os.makedirs(self.config['temp_dir'], exist_ok=True)

    def _load_config(self):
        """Загрузка конфигурации"""
        try:
            with open('config/config.yaml', 'r') as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {
                'temp_dir': '/app/temp',
                'youtube_api': {
                    'credentials_file': 'client_secrets.json',
                    'token_file': 'token.pickle'
                }
            }

    def _load_api_key(self):
        """Загрузка API ключа"""
        try:
            api_key = os.environ.get('YOUTUBE_API_KEY')
            if api_key:
                return api_key
                
            api_key_path = os.path.join('config', 'api.txt')
            if os.path.exists(api_key_path):
                with open(api_key_path, 'r') as f:
                    return f.read().strip()
            
            raise ValueError("YouTube API key not found")
        except Exception as e:
            self.logger.error(f"Error loading API key: {e}")
            raise

    def _load_client_secrets(self):
        """Загрузка client secrets"""
        try:
            secrets_path = self.config['youtube_api']['credentials_file']
            if os.path.exists(secrets_path):
                with open(secrets_path, 'r') as f:
                    return json.load(f)
            self.logger.warning("Client secrets file not found")
            return None
        except Exception as e:
            self.logger.error(f"Error loading client secrets: {e}")
            return None

    def initialize_api(self):
        """Инициализация YouTube API"""
        try:
            self.youtube = build('youtube', 'v3', developerKey=self.api_key)
            self.logger.info("YouTube API initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing YouTube API: {e}")
            raise

    def get_video_info(self, video_id, user_cookies=None):
        """
        Получает информацию о видео с учетом cookies пользователя
        
        Args:
            video_id (str): ID видео
            user_cookies (dict, optional): Cookies пользователя
        """
        cookies_file = None
        try:
            # Настройки для yt-dlp
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            }
            
            # Если переданы cookies пользователя, используем их
            if user_cookies:
                cookies_file = os.path.join(self.config['temp_dir'], f'cookies_{video_id}.txt')
                with open(cookies_file, 'w') as f:
                    json.dump(user_cookies, f)
                ydl_opts['cookiefile'] = cookies_file
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                if not info:
                    raise ValueError("Failed to extract video info")
                    
                return {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'duration': info.get('duration'),
                    'url': info.get('url'),
                    'thumbnail': info.get('thumbnail'),
                    'description': info.get('description')
                }
            
        except Exception as e:
            self.logger.error(f"Error getting video info: {str(e)}")
            return None
        finally:
            # Удаляем временный файл с cookies
            if cookies_file and os.path.exists(cookies_file):
                try:
                    os.remove(cookies_file)
                except Exception as e:
                    self.logger.error(f"Error removing cookies file: {e}")

    def get_download_url(self, video_id):
        """Получает прямую ссылку на скачивание"""
        try:
            info = self.get_video_info(video_id)
            if not info:
                raise ValueError("Failed to get video info")
                
            return {
                'url': info['url'],
                'title': info['title']
            }
        except Exception as e:
            self.logger.error(f"Error getting download URL: {e}")
            return None, str(e)

    def cleanup(self):
        """Очистка ресурсов"""
        try:
            if self.youtube:
                self.youtube.close()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
