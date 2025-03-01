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

            # Получаем путь к файлу с куками в формате Netscape
            netscape_cookie_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'youtube_netscape.cookies')
            self.logger.info(f"Using Netscape cookies from: {netscape_cookie_file}")
            
            # Настройки для yt-dlp с использованием файла куки
            ydl_opts = {
                'format': 'best',
                'outtmpl': output_path,
                'quiet': False,  # Включаем вывод для отладки
                'no_warnings': False,  # Включаем предупреждения для отладки
                'ignoreerrors': True,  # Игнорируем ошибки
                'skip_download': False,
                'noplaylist': True,
                'nocheckcertificate': True,
                'no_color': True,
                'verbose': True,  # Подробный вывод для отладки
                'cookiefile': netscape_cookie_file if os.path.exists(netscape_cookie_file) else None,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            }
            
            # Скачиваем видео
            self.logger.info(f"Starting download of {url} with yt-dlp")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Проверяем, что файл скачался
            if os.path.exists(output_path):
                self.logger.info(f"Video downloaded successfully: {output_path}")
                return True
            else:
                # Если файл не скачался, пробуем другой формат
                self.logger.warning(f"File not found at {output_path}, trying different format")
                
                # Пробуем скачать в формате mp4
                ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                    
                if os.path.exists(output_path):
                    self.logger.info(f"Video downloaded successfully with alternative format: {output_path}")
                    return True
                else:
                    raise FileNotFoundError(f"Failed to download video to {output_path}")
                
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
                        
                        # Преобразуем в формат для yt-dlp (Netscape cookie file format)
                        netscape_cookies = []
                        for cookie in cookies:
                            if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                                domain = cookie.get('domain', '.youtube.com')
                                path = cookie.get('path', '/')
                                secure = 'TRUE' if cookie.get('secure', True) else 'FALSE'
                                expiry = cookie.get('expiry', 0)
                                netscape_cookies.append(
                                    f"{domain}\tTRUE\t{path}\t{secure}\t{expiry}\t{cookie['name']}\t{cookie['value']}"
                                )
                        
                        # Сохраняем в формате Netscape для yt-dlp
                        netscape_cookie_file = os.path.join(os.path.dirname(cookie_file), 'youtube_netscape.cookies')
                        with open(netscape_cookie_file, 'w') as nf:
                            nf.write("\n".join(netscape_cookies))
                        
                        self.logger.info(f"Converted cookies to Netscape format at {netscape_cookie_file}")
                        
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
                        
                        # Преобразуем в формат для yt-dlp (Netscape cookie file format)
                        netscape_cookies = []
                        for cookie in formatted_cookies:
                            domain = cookie.get('domain', '.youtube.com')
                            path = cookie.get('path', '/')
                            secure = 'TRUE'
                            expiry = 0
                            netscape_cookies.append(
                                f"{domain}\tTRUE\t{path}\t{secure}\t{expiry}\t{cookie['name']}\t{cookie['value']}"
                            )
                        
                        # Сохраняем в формате Netscape для yt-dlp
                        netscape_cookie_file = os.path.join(os.path.dirname(cookie_file), 'youtube_netscape.cookies')
                        with open(netscape_cookie_file, 'w') as nf:
                            nf.write("\n".join(netscape_cookies))
                        
                        self.logger.info(f"Converted cookies to Netscape format at {netscape_cookie_file}")
                        
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