import os
import logging
import subprocess
from pathlib import Path
import shutil

logger = logging.getLogger(__name__)

class AudioExtractor:
    def __init__(self, temp_dir):
        """
        Инициализация экстрактора аудио
        
        Args:
            temp_dir (str): Путь к временной директории
        """
        self.temp_dir = temp_dir
        os.makedirs(temp_dir, exist_ok=True)
        self._check_ffmpeg()
        
    def _check_ffmpeg(self):
        """Проверка наличия и версии ffmpeg"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'], 
                capture_output=True, 
                text=True,
                check=True
            )
            version = result.stdout.split('version')[1].split()[0]
            logger.info(f"FFmpeg version: {version}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg check failed: {e.stderr}")
            raise RuntimeError("FFmpeg is not available")
        except Exception as e:
            logger.error(f"Error checking FFmpeg: {e}")
            raise RuntimeError("FFmpeg check failed")
        
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
                raise FileNotFoundError(f"Video file not found: {video_path}")
                
            # Создаем уникальное имя для аудио файла
            video_name = Path(video_path).stem
            audio_path = os.path.join(self.temp_dir, f'{video_name}_audio.wav')
            
            # Проверяем достаточно ли места на диске
            self._check_disk_space(video_path)
            
            # Настройки FFmpeg для качественного аудио
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
                error_msg = process.stderr or "Unknown FFmpeg error"
                logger.error(f"FFmpeg failed: {error_msg}")
                raise RuntimeError(f"Failed to extract audio: {error_msg}")
                
            if not os.path.exists(audio_path):
                raise RuntimeError("Audio file was not created")
                
            logger.info(f"Audio extracted successfully to {audio_path}")
            return audio_path
            
        except Exception as e:
            logger.error(f"Error in audio extraction: {str(e)}")
            self._cleanup_temp_files()
            raise
            
    def _check_disk_space(self, video_path):
        """Проверка свободного места на диске"""
        try:
            video_size = os.path.getsize(video_path)
            free_space = shutil.disk_usage(self.temp_dir).free
            
            # Требуем в 2 раза больше места, чем размер видео
            required_space = video_size * 2
            
            if free_space < required_space:
                raise RuntimeError(
                    f"Insufficient disk space. Required: {required_space/1024/1024:.1f}MB, "
                    f"Available: {free_space/1024/1024:.1f}MB"
                )
        except Exception as e:
            logger.error(f"Error checking disk space: {e}")
            raise
            
    def _cleanup_temp_files(self):
        """Очистка временных файлов"""
        try:
            for file in os.listdir(self.temp_dir):
                if file.endswith('.wav'):
                    file_path = os.path.join(self.temp_dir, file)
                    try:
                        os.remove(file_path)
                        logger.info(f"Removed temporary file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to remove temporary file {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error cleaning temporary files: {e}")