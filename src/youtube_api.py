import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
import time

MAX_TOKEN_REFRESH_ATTEMPTS = 3

class YouTubeAPI:
    def __init__(self):
        self.api_key = self._load_api_key()
        self.credentials = None
        self.youtube = None
        
    def _load_api_key(self):
        """Загрузка API ключа из файла"""
        try:
            with open('api.txt', 'r') as f:
                return f.read().strip()
        except FileNotFoundError:
            raise Exception("API key file (api.txt) not found")

    def authenticate(self):
        """OAuth2 аутентификация"""
        for attempt in range(MAX_TOKEN_REFRESH_ATTEMPTS):
            try:
                creds = None
                if os.path.exists('token.pickle'):
                    with open('token.pickle', 'rb') as token:
                        creds = pickle.load(token)

                if not creds or not creds.valid:
                    if creds and creds.expired and creds.refresh_token:
                        creds.refresh(Request())
                    else:
                        flow = InstalledAppFlow.from_client_secrets_file(
                            'client_secrets.json',
                            ['https://www.googleapis.com/auth/youtube.readonly']
                        )
                        creds = flow.run_local_server(port=8080)
                        
                    with open('token.pickle', 'wb') as token:
                        pickle.dump(creds, token)

                self.credentials = creds
                self.youtube = build('youtube', 'v3', credentials=creds)
                return True
            except Exception as e:
                if attempt == MAX_TOKEN_REFRESH_ATTEMPTS - 1:
                    raise RuntimeError(f"Не удалось обновить токен после {MAX_TOKEN_REFRESH_ATTEMPTS} попыток")
                time.sleep(2 ** attempt)

    def get_video_info(self, video_id):
        """Получает информацию о видео"""
        if not self.youtube:
            self.authenticate()
            
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
            return None, str(e)

    def get_download_url(self, video_id):
        """Получает прямую ссылку на скачивание"""
        info, error = self.get_video_info(video_id)
        if error:
            return None, error
            
        # Возвращаем прямую ссылку на видео
        download_url = f"https://www.youtube.com/watch?v={video_id}"
        return download_url, info['title']
