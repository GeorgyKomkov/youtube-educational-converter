import os
import sys
import logging
import yaml
import uuid
import re
import cv2
import torch
import subprocess
import urllib.parse
import yt_dlp
import gc
import resource
import shutil
from pathlib import Path
from os import statvfs
import whisper
from whisper import load_model
import logging.config

# Импортируем наши модули
from .audio_extractor import AudioExtractor
from .frame_processor import FrameProcessor
from .output_generator import OutputGenerator
from .youtube_api import YouTubeAPI

# Настройка логирования
logger = logging.getLogger(__name__)

# Кэш для моделей Whisper
class WhisperModelCache:
    _models = {}
    
    @classmethod
    def get_model(cls, model_name, device):
        """Получение модели Whisper из кэша или загрузка новой"""
        key = f"{model_name}_{device}"
        if key not in cls._models:
            logger.info(f"Loading Whisper model: {model_name} on {device}")
            cls._models[key] = whisper.load_model(model_name, device=device)
        return cls._models[key]
    
    @classmethod
    def clear_cache(cls):
        """Очистка кэша моделей"""
        cls._models.clear()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

# Основной класс для обработки видео
class VideoProcessor:
    def __init__(self, config=None):
        """
        Инициализация процессора видео
        
        Args:
            config (dict, optional): Конфигурация. Если None, загружается из файла.
        """
        self.logger = logging.getLogger(__name__)
        
        # Загружаем конфигурацию, если не передана
        if config is None:
            self.config = self._load_config()
        else:
            self.config = config
            
        # Инициализируем пути
        self.temp_dir = self.config.get('temp_dir', '/tmp/video_processor')
        self.output_dir = self.config.get('output_dir', '/tmp/video_output')
        
        # Создаем директории
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Инициализируем компоненты
        self.youtube_api = YouTubeAPI()
        self.audio_extractor = AudioExtractor(self.temp_dir)
        self.frame_processor = FrameProcessor(self.output_dir)
        self.output_generator = OutputGenerator(self.output_dir)
        
        # Проверяем зависимости
        self._check_dependencies()
        
    def _load_config(self):
        """Загрузка конфигурации из YAML файла"""
        try:
            config_path = os.path.join('config', 'config.yaml')
            if not os.path.exists(config_path):
                raise FileNotFoundError(f"Config file not found: {config_path}")
                
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                
            # Проверка обязательных параметров
            required = ['temp_dir', 'output_dir']
            missing = [param for param in required if param not in config]
            if missing:
                raise ValueError(f"Missing required parameters: {', '.join(missing)}")
                
            return config
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            # Возвращаем базовую конфигурацию
            return {
                'temp_dir': '/tmp/video_processor',
                'output_dir': '/tmp/video_output',
                'transcription': {
                    'model': 'small',
                    'use_gpu': True
                },
                'video_processing': {
                    'max_frames': 10
                }
            }
            
    def _check_dependencies(self):
        """Проверка наличия необходимых зависимостей"""
        try:
            # Проверка FFmpeg
            try:
                result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
                if result.returncode != 0:
                    self.logger.warning("FFmpeg not found or not working properly")
            except Exception:
                self.logger.warning("FFmpeg check failed")
                
            # Проверка yt-dlp
            try:
                result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True)
                if result.returncode != 0:
                    self.logger.warning("yt-dlp not found or not working properly")
            except Exception:
                self.logger.warning("yt-dlp check failed")
                
            # Проверка доступности GPU
            if torch.cuda.is_available():
                self.logger.info(f"GPU available: {torch.cuda.get_device_name(0)}")
            else:
                self.logger.info("GPU not available, using CPU")
                
        except Exception as e:
            self.logger.error(f"Error checking dependencies: {e}")
            
    def process_video(self, url):
        """
        Обработка видео
        
        Args:
            url (str): URL видео или путь к локальному файлу
            
        Returns:
            dict: Результат обработки
        """
        try:
            # Создаем временную директорию для файлов
            temp_dir = os.path.join(self.temp_dir, str(uuid.uuid4()))
            os.makedirs(temp_dir, exist_ok=True)
            
            # Определяем, является ли url локальным файлом
            is_local_file = os.path.exists(url)
            
            if is_local_file:
                video_path = url
                video_title = os.path.basename(url).split('.')[0]
            else:
                # Извлекаем ID видео (если это YouTube URL)
                video_id = self._extract_video_id(url) if 'youtube.com' in url or 'youtu.be' in url else None
                
                # Получаем заголовок видео
                if video_id:
                    try:
                        video_info = self.youtube_api.get_video_info(video_id)
                        video_title = video_info.get('title', f"Video_{video_id}")
                    except Exception as e:
                        self.logger.warning(f"Could not get video info: {e}")
                        video_title = f"Video_{video_id if video_id else uuid.uuid4()}"
                else:
                    video_title = f"Video_{uuid.uuid4()}"
                    
                self.logger.info(f"Processing video: {video_title}")
                
                # Загружаем видео
                video_path = self._download_video(url)
                if not video_path:
                    # Если не удалось загрузить, создаем пустое видео
                    self.logger.warning("Failed to download video, creating empty video")
                    video_path = self._create_empty_video(temp_dir)
                    if not video_path:
                        raise ValueError("Failed to create empty video")
            
            # Извлекаем аудио
            audio_path = self._extract_audio(video_path)
            
            # Если не удалось извлечь аудио, создаем пустой файл
            if not audio_path:
                self.logger.warning("Failed to extract audio, creating empty audio file")
                audio_path = self.audio_extractor._create_empty_audio()
                transcription = "Не удалось извлечь аудио из видео."
            else:
                # Транскрибируем аудио
                transcription = self._transcribe_audio(audio_path)
                
            # Если не удалось транскрибировать, используем заглушку
            if not transcription:
                transcription = "Не удалось распознать речь в видео."
                
            # Извлекаем кадры
            frames = self._extract_frames(video_path)
            
            # Если не удалось извлечь кадры, используем заглушку
            if not frames or len(frames) == 0:
                self.logger.warning("Failed to extract frames, using placeholder")
                frames = []
                
            # Генерируем выходной файл
            output_path = self._generate_pdf(transcription, frames, video_title)
            
            # Очищаем временные файлы
            self._cleanup_temp_files(temp_dir)
            
            return {
                'status': 'completed',
                'output_path': str(output_path),
                'video_title': video_title
            }
            
        except Exception as e:
            self.logger.error(f"Error processing video: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
            
    def _extract_video_id(self, url):
        """Извлечение ID видео из URL"""
        try:
            self.logger.info(f"Extracting video ID from URL: {url}")
            
            # Проверяем, является ли URL полным URL YouTube
            youtube_patterns = [
                r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([^&\s]+)',
                r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([^\?\s]+)',
                r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([^\?\s]+)',
                r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/v\/([^\?\s]+)',
                r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/user\/[^\/]+\/\?v=([^\&\s]+)',
                r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([^\?\s]+)'
            ]
            
            # Проверяем каждый паттерн
            for pattern in youtube_patterns:
                match = re.search(pattern, url)
                if match:
                    video_id = match.group(1)
                    self.logger.info(f"Extracted video ID: {video_id}")
                    return video_id
            
            # Если не удалось извлечь ID по паттернам, пробуем через urllib.parse
            parsed_url = urllib.parse.urlparse(url)
            if parsed_url.netloc in ['youtube.com', 'www.youtube.com']:
                query_params = urllib.parse.parse_qs(parsed_url.query)
                if 'v' in query_params:
                    video_id = query_params['v'][0]
                    self.logger.info(f"Extracted video ID: {video_id}")
                    return video_id
            
            # Если URL не содержит ID, возможно это и есть ID
            if re.match(r'^[a-zA-Z0-9_-]{11}$', url):
                self.logger.info(f"URL appears to be a video ID: {url}")
                return url
                
            self.logger.error(f"Could not extract video ID from URL: {url}")
            return None
        except Exception as e:
            self.logger.error(f"Error extracting video ID: {e}")
            return None
            
    def _download_video(self, url):
        """Загрузка видео с YouTube с ограничением качества"""
        try:
            self.logger.info(f"Downloading video from URL: {url}")
            
            # Создаем временную директорию
            temp_dir = os.path.join(self.temp_dir, str(uuid.uuid4()))
            os.makedirs(temp_dir, exist_ok=True)
            
            # Настройки для yt-dlp с сильным ограничением качества для экономии ресурсов
            ydl_opts = {
                'format': 'worst[height<=360]',  # Используем самое низкое качество
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
            }
            
            # Загружаем видео
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not info:
                        self.logger.warning(f"Could not extract video info from URL: {url}")
                        return None
                    
                    video_path = os.path.join(temp_dir, f"{info['title']}.{info['ext']}")
                    
                    # Проверяем, что файл существует и не пустой
                    if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
                        self.logger.warning(f"Downloaded video file not found or empty: {video_path}")
                        return None
                    
                    self.logger.info(f"Video downloaded successfully: {video_path}")
                    return video_path
            except Exception as e:
                self.logger.error(f"Error downloading video with yt-dlp: {e}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error downloading video: {e}")
            return None
            
    def _create_empty_video(self, temp_dir):
        """Создание пустого видео файла для продолжения обработки"""
        try:
            self.logger.warning("Creating empty video file as fallback")
            output_path = os.path.join(temp_dir, "empty_video.mp4")
            
            # Создаем пустое видео длительностью 1 секунда
            command = [
                'ffmpeg',
                '-y',
                '-f', 'lavfi',
                '-i', 'color=c=black:s=1280x720:r=30',
                '-t', '1',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                output_path
            ]
            
            process = subprocess.run(command, capture_output=True, text=True)
            
            if process.returncode != 0:
                self.logger.error(f"Failed to create empty video: {process.stderr}")
                raise RuntimeError("Could not create empty video file")
                
            return output_path
        except Exception as e:
            self.logger.error(f"Failed to create empty video: {e}")
            return None
            
    def _extract_audio(self, video_path):
        """Извлечение аудио из видео"""
        try:
            self.logger.info(f"Extracting audio from video: {video_path}")
            return self.audio_extractor.extract(video_path)
        except Exception as e:
            self.logger.error(f"Error extracting audio: {e}")
            return None
            
    def _transcribe_audio(self, audio_path):
        """Транскрибация аудио"""
        try:
            self.logger.info(f"Transcribing audio: {audio_path}")
            
            model_name = self.config.get('transcription', {}).get('model', 'small')
            use_gpu = self.config.get('transcription', {}).get('use_gpu', False)
            device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
            
            model = WhisperModelCache.get_model(model_name, device)
            result = model.transcribe(audio_path)
            
            # Извлекаем текст из результата
            if isinstance(result, dict) and 'text' in result:
                return result['text']
            elif isinstance(result, dict) and 'segments' in result:
                return ' '.join([segment.get('text', '') for segment in result['segments']])
            else:
                return str(result)
                
        except Exception as e:
            self.logger.error(f"Error transcribing audio: {e}")
            return None
            
    def _extract_frames(self, video_path):
        """Извлечение и обработка кадров"""
        try:
            self.logger.info(f"Extracting frames from video: {video_path}")
            return self.frame_processor.process(video_path)
        except Exception as e:
            self.logger.error(f"Error extracting frames: {e}")
            return []
            
    def _generate_pdf(self, transcription, frames, video_title):
        """Генерация PDF отчета"""
        try:
            self.logger.info(f"Generating PDF for video: {video_title}")
            return self.output_generator.generate_output(transcription, frames, video_title)
        except Exception as e:
            self.logger.error(f"Error generating PDF: {e}")
            # Создаем простой текстовый файл как запасной вариант
            output_path = os.path.join(self.output_dir, f"{video_title}.txt")
            with open(output_path, 'w') as f:
                f.write(f"Заголовок: {video_title}\n\n")
                f.write(f"Транскрипция:\n{transcription}\n\n")
                f.write(f"Количество кадров: {len(frames)}")
            return output_path
            
    def _cleanup_temp_files(self, temp_dir):
        """Очистка временных файлов"""
        try:
            self.logger.info(f"Cleaning up temporary files in: {temp_dir}")
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            self.logger.error(f"Error cleaning up temporary files: {e}")