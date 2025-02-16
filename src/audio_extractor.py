import os
import logging
from pydub import AudioSegment

logger = logging.getLogger(__name__)

class AudioExtractor:
    def __init__(self, temp_dir):
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)
        
    def extract(self, video_path):
        """Извлекает аудио из видео"""
        try:
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Видео файл не найден: {video_path}")
                
            audio_path = os.path.join(self.temp_dir, 'audio.wav')
            
            # Используем ffmpeg для извлечения аудио
            os.system(f'ffmpeg -i "{video_path}" -vn -acodec pcm_s16le -ar 44100 -ac 2 "{audio_path}"')
            
            if not os.path.exists(audio_path):
                raise Exception("Не удалось извлечь аудио из видео")
                
            return audio_path
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении аудио: {e}")
            raise