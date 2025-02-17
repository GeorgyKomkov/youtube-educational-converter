import os
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class AudioExtractor:
    def __init__(self, temp_dir):
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)
        self._check_ffmpeg()
        
    def _check_ffmpeg(self):
        """Проверка наличия и версии ffmpeg"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                 capture_output=True, 
                                 text=True)
            if result.returncode != 0:
                raise RuntimeError("FFmpeg не установлен")
            logger.info(f"FFmpeg version: {result.stdout.split('version')[1].split()[0]}")
        except Exception as e:
            logger.error(f"Ошибка при проверке FFmpeg: {e}")
            raise RuntimeError("FFmpeg не доступен")
        
    def extract(self, video_path):
        """
        Извлекает аудио из видео используя ffmpeg
        
        Args:
            video_path (str): Путь к видео файлу
            
        Returns:
            str: Путь к извлеченному аудио файлу
            
        Raises:
            FileNotFoundError: Если видео файл не найден
            RuntimeError: Если не удалось извлечь аудио
        """
        try:
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Видео файл не найден: {video_path}")
                
            audio_path = os.path.join(self.temp_dir, 'audio.wav')
            
            # Используем subprocess для безопасного запуска ffmpeg
            command = [
                'ffmpeg',
                '-i', video_path,
                '-vn',                # Отключаем видео
                '-acodec', 'pcm_s16le', # Кодек для WAV
                '-ar', '44100',      # Частота дискретизации
                '-ac', '2',          # Количество каналов
                '-y',                # Перезаписывать существующие файлы
                audio_path
            ]
            
            logger.info(f"Extracting audio from {video_path}")
            process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False  # Не вызывать исключение автоматически
            )
            
            if process.returncode != 0:
                error_msg = process.stderr or "Unknown ffmpeg error"
                logger.error(f"FFmpeg failed: {error_msg}")
                raise RuntimeError(f"Failed to extract audio: {error_msg}")
                
            if not os.path.exists(audio_path):
                raise RuntimeError("Audio file was not created")
                
            logger.info(f"Audio extracted successfully to {audio_path}")
            return audio_path
            
        except Exception as e:
            logger.error(f"Error in audio extraction: {str(e)}")
            raise