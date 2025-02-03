import os
import logging
import yt_dlp
from slugify import slugify

class VideoDownloader:
    def __init__(self, temp_dir, proxy=None):
        # Создание директории
        os.makedirs(temp_dir, exist_ok=True)
        
        self.temp_dir = temp_dir
        self.proxy = proxy
        self.logger = logging.getLogger(__name__)
        self.current_title = None

    def download(self, url):
        try:
            # Настройки загрузки
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
                'outtmpl': os.path.join(self.temp_dir, '%(title)s.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                'ignoreerrors': False,
                'proxy': self.proxy
            }
            
            # Загрузка видео
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # Безопасное имя файла
                safe_title = slugify(info['title'])
                filename = ydl.prepare_filename(info)
                
                # Проверки
                if not os.path.exists(filename):
                    raise ValueError("Файл видео не был создан")
                
                file_size = os.path.getsize(filename)
                if file_size < 1024:  # Минимальный размер 1 КБ
                    raise ValueError("Скачанный файл слишком мал")
                
                self.current_title = safe_title
                
                self.logger.info(f"Видео успешно скачано: {safe_title}")
                return filename, safe_title
        
        except Exception as e:
            self.logger.error(f"Ошибка при скачивании видео: {e}")
            raise

    def get_title(self):
        return self.current_title