import os
import logging
import subprocess
from pathlib import Path
from shutil import disk_usage

logger = logging.getLogger(__name__)

class AudioExtractor:
    def __init__(self, temp_dir):
        """
        Инициализация экстрактора аудио
        
        Args:
            temp_dir (str): Путь к временной директории
        """
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
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
            raise
        
    def extract(self, video_path):
        """
        Извлекает аудио из видео используя ffmpeg
        
        Args:
            video_path (str): Путь к видео файлу
            
        Returns:
            str: Путь к извлеченному аудио файлу
        """
        try:
            video_path = Path(video_path)
            if not video_path.exists():
                raise FileNotFoundError(f"Video file not found: {video_path}")
                
            # Проверка места на диске
            self._check_disk_space(video_path)
            
            # Путь к выходному файлу
            output_path = self.temp_dir / f"{Path(video_path).stem}.wav"
            
            # Добавляем параметры для обработки поврежденных файлов
            command = [
                'ffmpeg',
                '-err_detect', 'ignore_err',  # Игнорировать ошибки
                '-i', str(video_path),
                '-vn',
                '-ac', '1',  # моно
                '-ar', '16000',  # частота дискретизации
                '-b:a', '64k',  # низкий битрейт
                '-f', 'wav',
                str(output_path)
            ]
            
            # Запускаем процесс
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFmpeg failed: {stderr.decode()}")
                # Пробуем альтернативный метод
                return self._extract_alternative(video_path)
                
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Error in audio extraction: {str(e)}")
            self._cleanup_temp_files()
            raise
            
    def _check_disk_space(self, video_path):
        """Проверка свободного места на диске"""
        try:
            video_size = os.path.getsize(video_path)
            free_space = disk_usage(self.temp_dir).free
            
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
                    file_path = self.temp_dir / file
                    try:
                        file_path.unlink()
                        logger.info(f"Removed temporary file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to remove temporary file {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error cleaning temporary files: {e}")

    def _extract_alternative(self, video_path):
        """Альтернативный метод извлечения аудио с дополнительными параметрами"""
        try:
            logger.info("Trying alternative audio extraction method with more options")
            output_path = self.temp_dir / f"{Path(video_path).stem}_alt.wav"
            
            # Используем более надежные параметры для проблемных файлов
            command = [
                'ffmpeg',
                '-y',  # Перезаписывать выходной файл
                '-v', 'error',  # Выводить только ошибки
                '-err_detect', 'ignore_err',  # Игнорировать ошибки
                '-fflags', '+genpts+igndts+discardcorrupt',  # Игнорировать поврежденные данные
                '-i', str(video_path),
                '-vn',  # Без видео
                '-acodec', 'pcm_s16le',  # Кодек аудио
                '-ar', '16000',  # Частота дискретизации
                '-ac', '1',  # Моно
                '-f', 'wav',  # Формат выходного файла
                str(output_path)
            ]
            
            logger.info(f"Running command: {' '.join(command)}")
            process = subprocess.run(command, capture_output=True, text=True)
            
            if process.returncode != 0:
                logger.error(f"Alternative extraction failed: {process.stderr}")
                # Пробуем еще один метод с прямым извлечением аудио
                return self._extract_direct(video_path)
            
            return str(output_path)
        except Exception as e:
            logger.error(f"Alternative extraction failed: {e}")
            # Пробуем еще один метод
            return self._extract_direct(video_path)
        
    def _extract_direct(self, video_path):
        """Прямое извлечение аудио без перекодирования"""
        try:
            logger.info("Trying direct audio extraction without transcoding")
            output_path = self.temp_dir / f"{Path(video_path).stem}_direct.wav"
            
            # Просто копируем аудио поток без перекодирования
            command = [
                'ffmpeg',
                '-y',
                '-v', 'error',
                '-i', str(video_path),
                '-vn',
                '-acodec', 'copy',  # Копируем аудио без перекодирования
                str(output_path.with_suffix('.aac'))  # Сохраняем в оригинальном формате
            ]
            
            logger.info(f"Running command: {' '.join(command)}")
            process = subprocess.run(command, capture_output=True, text=True)
            
            if process.returncode != 0:
                logger.error(f"Direct extraction failed: {process.stderr}")
                # Пробуем создать пустой аудиофайл для продолжения обработки
                return self._create_empty_audio()
            
            # Теперь конвертируем в WAV
            aac_path = output_path.with_suffix('.aac')
            command = [
                'ffmpeg',
                '-y',
                '-v', 'error',
                '-i', str(aac_path),
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                str(output_path)
            ]
            
            process = subprocess.run(command, capture_output=True, text=True)
            
            if process.returncode != 0:
                logger.error(f"Conversion to WAV failed: {process.stderr}")
                return self._create_empty_audio()
            
            return str(output_path)
        except Exception as e:
            logger.error(f"Direct extraction failed: {e}")
            return self._create_empty_audio()
        
    def _create_empty_audio(self):
        """Создание пустого аудиофайла для продолжения обработки"""
        try:
            logger.warning("Creating empty audio file as fallback")
            output_path = self.temp_dir / "empty_audio.wav"
            
            # Создаем пустой аудиофайл длительностью 1 секунда
            command = [
                'ffmpeg',
                '-y',
                '-f', 'lavfi',
                '-i', 'anullsrc=r=16000:cl=mono',
                '-t', '1',
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                str(output_path)
            ]
            
            process = subprocess.run(command, capture_output=True, text=True)
            
            if process.returncode != 0:
                logger.error(f"Failed to create empty audio: {process.stderr}")
                raise RuntimeError("Could not create empty audio file")
            
            return str(output_path)
        except Exception as e:
            logger.error(f"Failed to create empty audio: {e}")
            raise