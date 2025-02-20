import os
import logging.config
import redis
from googleapiclient.discovery import build
import yt_dlp
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

class YouTubeAPI:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config()
        self._setup_http_session()
        self._setup_redis()
        self._setup_api()
        
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
        """Инициализация YouTube API"""
        try:
            api_key = self._load_api_key()
            if not api_key:
                raise ValueError("YouTube API key not found")
                
            self.youtube = build(
                'youtube', 
                'v3', 
                developerKey=api_key,
                cache_discovery=False
            )
        except Exception as e:
            self.logger.error(f"YouTube API setup failed: {e}")
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

    def download_video(self, video_url, output_path):
        """Загрузка видео с обработкой ошибок"""
        try:
            ydl_opts = {
                'format': 'best[height<=720]',
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
                'cookiefile': 'config/cookies.txt'
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([video_url])
                except Exception as e:
                    self.logger.error(f"yt-dlp download failed: {e}")
                    raise
                
            if not os.path.exists(output_path):
                raise FileNotFoundError(f"Download completed but file not found: {output_path}")
                
            return output_path
            
        except Exception as e:
            self.logger.error(f"Video download failed: {e}")
            raise

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
