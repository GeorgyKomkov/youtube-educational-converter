import os
import logging
import yt_dlp
from slugify import slugify

class VideoDownloader:
    def __init__(self, temp_dir, proxy=None):
        os.makedirs(temp_dir, exist_ok=True)
        
        self.temp_dir = temp_dir
        self.proxy = proxy
        self.logger = logging.getLogger(__name__)
        self.current_title = None

    def download(self, url):
        """Скачивает видео с YouTube с ограничением качества до 720p"""
        try:
            self.logger.info(f"Попытка скачать видео: {url}")

            ydl_opts = {
                'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
                'outtmpl': os.path.join(self.temp_dir, '%(title)s.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                'ignoreerrors': False,
                'proxy': self.proxy
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if 'entries' in info:
                    info = info['entries'][0]
                if not info or 'url' not in info:
                    self.logger.warning("Видео недоступно или удалено.")
                    raise ValueError("Видео недоступно или удалено.")

                self.logger.info("Видео доступно, начинаем скачивание...")

                # Теперь скачиваем
                info = ydl.extract_info(url, download=True)
                
                safe_title = slugify(info['title'])
                filename = ydl.prepare_filename(info)
                
                if not os.path.exists(filename):
                    self.logger.error("Файл видео не был создан.")
                    raise ValueError("Файл видео не был создан")
                
                file_size = os.path.getsize(filename)
                if file_size < 1024:
                    self.logger.error("Скачанный файл слишком мал.")
                    raise ValueError("Скачанный файл слишком мал")
                
                self.current_title = safe_title
                self.logger.info(f"Видео успешно скачано: {safe_title}")
                
                return filename, safe_title
        
        except Exception as e:
            self.logger.error(f"Ошибка при скачивании видео: {e}")
            raise

    def get_title(self):
        return self.current_title
