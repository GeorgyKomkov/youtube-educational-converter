import os
import json
import logging
from googleapiclient.discovery import build

class YouTubeAPI:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.youtube = None
        self.api_key = self._load_api_key()
        self.client_secrets = self._load_client_secrets()
        self.initialize_api()

    def _load_api_key(self):
        """Загрузка API ключа из файла"""
        try:
            with open('api.txt', 'r') as f:
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
        """Получает информацию о видео"""
        try:
            request = self.youtube.videos().list(
                part="snippet,contentDetails",
                id=video_id
            )
            response = request.execute()
            
            if not response.get('items'):
                return None, "Видео не найдено"
                
            video_info = response['items'][0]
            return {
                'title': video_info['snippet']['title'],
                'duration': video_info['contentDetails']['duration'],
                'description': video_info['snippet']['description']
            }, None
            
        except Exception as e:
            self.logger.error(f"Error getting video info: {e}")
            return None, str(e)

    def get_download_url(self, video_id):
        """Получает прямую ссылку на скачивание"""
        info, error = self.get_video_info(video_id)
        if error:
            return None, error
            
        # Возвращаем прямую ссылку на видео
        download_url = f"https://www.youtube.com/watch?v={video_id}"
        return download_url, info['title']
