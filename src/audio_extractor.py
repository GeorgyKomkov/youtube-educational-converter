import os
import logging
import shutil
import subprocess
from pathlib import Path

class AudioExtractor:
    def __init__(self, temp_dir):
        self.temp_dir = temp_dir
        self.logger = logging.getLogger(__name__)
        os.makedirs(temp_dir, exist_ok=True)

    def extract(self, video_path):
        try:
            # Проверка FFmpeg
            if not shutil.which('ffmpeg'):
                raise RuntimeError("FFmpeg не установлен")
            
            # Путь для аудио
            audio_path = os.path.join(
                self.temp_dir, 
                Path(video_path).stem + '.wav'
            )
            
            # Команда извлечения
            cmd = [
                'ffmpeg', 
                '-i', video_path, 
                '-vn',  # без видео
                '-acodec', 'pcm_s16le',  # формат аудио
                '-ar', '16000',  # частота дискретизации
                '-y',  # принудительная перезапись
                audio_path
            ]
            
            # Выполнение команды
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                check=True
            )
            
            # Проверки
            if not os.path.exists(audio_path):
                raise RuntimeError("Аудиофайл не создан")
            
            audio_size = os.path.getsize(audio_path)
            if audio_size < 1024:  # Минимальный размер 1 КБ
                raise RuntimeError("Извлеченный аудиофайл слишком мал")
            
            self.logger.info(f"Аудио успешно извлечено: {audio_path}")
            return audio_path
        
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr[:500] if e.stderr else 'Unknown error'
            self.logger.error(f"Ошибка FFmpeg: {error_msg}")
            raise
        
        except Exception as e:
            self.logger.error(f"Ошибка при извлечении аудио: {e}")
            raise