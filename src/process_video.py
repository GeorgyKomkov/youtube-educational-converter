import yaml
import os
import sys
import logging
from pathlib import Path
import torch
from os import statvfs
from .audio_extractor import AudioExtractor
from .frame_processor import FrameProcessor
from .output_generator import OutputGenerator
import whisper
from whisper import load_model
import logging.config
import shutil
import cv2
import resource
import gc
import yt_dlp  # Добавим импорт
import uuid
from .youtube_api import YouTubeAPI
import json
import subprocess
import re
import urllib.parse

# Настройка логирования
def setup_logging():
    try:
        with open('config/logging.yaml', 'r') as f:
            config = yaml.safe_load(f)
        logging.config.dictConfig(config)
    except Exception as e:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        logging.error(f"Error setting up logging: {e}")

# Инициализация логгера
setup_logging()
logger = logging.getLogger(__name__)

def load_config():
    """Загрузка конфигурации из YAML файла"""
    try:
        config_path = os.path.join('config', 'config.yaml')
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")
            
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        # Проверка обязательных параметров
        required = ['temp_dir', 'output_dir', 'transcription', 'video_processing']
        for param in required:
            if param not in config:
                raise ValueError(f"Missing required parameter: {param}")
                
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {
            'temp_dir': 'temp',
            'output_dir': 'output',
            'transcription': {'model': 'base', 'use_gpu': False},
            'video_processing': {'max_frames': 20}
        }

# Загрузка конфигурации
config = load_config()

def check_disk_space(path, required_mb=1000):
    """Проверка свободного места на диске"""
    try:
        stats = statvfs(path)
        free_mb = (stats.f_bavail * stats.f_frsize) / (1024 * 1024)
        if free_mb < required_mb:
            raise RuntimeError(f"Insufficient disk space. Required: {required_mb}MB, Available: {free_mb:.2f}MB")
        return True
    except Exception as e:
        logger.error(f"Error checking disk space: {e}")
        raise

class WhisperModelCache:
    _instance = None
    _model = None
    
    @classmethod
    def get_model(cls, model_name, device):
        if cls._model is None:
            try:
                cls._model = load_model(model_name, device=device)
            except Exception as e:
                logger.error(f"Error loading Whisper model: {e}")
                raise
        return cls._model

    @classmethod
    def cleanup(cls):
        if cls._model is not None:
            try:
                del cls._model
                cls._model = None
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception as e:
                logger.error(f"Error cleaning up Whisper model: {e}")

def cleanup_temp(temp_dir):
    """Очистка временных файлов"""
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            os.makedirs(temp_dir)
            logger.info(f"Temporary directory cleaned: {temp_dir}")
    except Exception as e:
        logger.error(f"Error cleaning temp directory: {e}")
        raise

class VideoProcessor:
    def __init__(self, config):
        """Инициализация процессора видео"""
        self.config = config
        self.temp_dir = config.get('temp_dir', '/app/temp')
        self.output_dir = config.get('output_dir', '/app/output')
        self.logger = logging.getLogger(__name__)
        
        # Создаем директории, если они не существуют
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Инициализируем экстрактор аудио
        self.audio_extractor = AudioExtractor(self.temp_dir)
        
        # Инициализируем генератор выходных данных
        self.output_generator = OutputGenerator(self.output_dir)
        
        # Проверяем наличие необходимых инструментов
        self._check_dependencies()
        
        # Инициализируем YouTube API
        self.youtube_api = YouTubeAPI()
    
    def _check_dependencies(self):
        """Проверка наличия необходимых инструментов"""
        try:
            # Проверяем ffmpeg
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            self.logger.info("ffmpeg is available")
            
            # Проверяем yt-dlp
            try:
                subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
                self.logger.info("yt-dlp is available")
            except (subprocess.SubprocessError, FileNotFoundError):
                self.logger.warning("yt-dlp is not available")
            
            # Проверяем youtube-dl
            try:
                subprocess.run(['youtube-dl', '--version'], capture_output=True, check=True)
                self.logger.info("youtube-dl is available")
            except (subprocess.SubprocessError, FileNotFoundError):
                self.logger.warning("youtube-dl is not available")
                
        except Exception as e:
            self.logger.error(f"Error checking dependencies: {e}")
            raise

    def download_video(self, video_url):
        """Download video from YouTube"""
        try:
            # Загружаем cookies из файла
            cookies_path = Path('config/youtube.cookies')
            if not cookies_path.exists():
                logger.warning("YouTube cookies file not found")
            
            ydl_opts = {
                'format': 'best',
                'outtmpl': str(self.temp_dir / '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'cookiefile': str(cookies_path),  # Добавляем путь к файлу с cookies
                'nocheckcertificate': True,
                'ignoreerrors': True,
                'extract_flat': False,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            }
            
            logger.info(f"Downloading video from URL: {video_url}")
            logger.info(f"Using cookies from: {cookies_path}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                video_path = self.temp_dir / f"{info['id']}.{info['ext']}"
                logger.info(f"Video downloaded successfully to: {video_path}")
                return str(video_path)
                
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            if hasattr(e, 'msg'):
                logger.error(f"Error message: {e.msg}")
            raise RuntimeError(f"Failed to download video: {str(e)}")

    def download_video_alternative(self, url):
        """Альтернативный метод загрузки видео"""
        try:
            self.logger.info(f"Trying alternative download method for URL: {url}")
            
            # Создаем временную директорию
            temp_dir = os.path.join(self.temp_dir, str(uuid.uuid4()))
            os.makedirs(temp_dir, exist_ok=True)
            
            # Имя выходного файла
            output_path = os.path.join(temp_dir, f"video_{uuid.uuid4()}.mp4")
            
            # Пробуем использовать youtube-dl напрямую
            try:
                self.logger.info("Trying youtube-dl for download")
                command = [
                    'youtube-dl',
                    '--format', 'best[ext=mp4]/best',
                    '--output', output_path,
                    '--no-playlist',
                    '--no-warnings',
                    '--no-check-certificate',
                    '--prefer-insecure',
                    url
                ]
                
                process = subprocess.run(command, capture_output=True, text=True)
                
                if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    self.logger.info(f"Video downloaded successfully with youtube-dl: {output_path}")
                    return output_path
                else:
                    self.logger.error(f"youtube-dl download failed: {process.stderr}")
            except Exception as e:
                self.logger.error(f"Error using youtube-dl: {e}")
            
            # Пробуем использовать curl
            try:
                self.logger.info("Trying curl for direct download")
                # Проверяем, что URL указывает на файл напрямую
                if url.endswith('.mp4') or url.endswith('.avi') or url.endswith('.mov'):
                    command = [
                        'curl',
                        '-L',
                        '-o', output_path,
                        url
                    ]
                    
                    process = subprocess.run(command, capture_output=True, text=True)
                    
                    if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        self.logger.info(f"Video downloaded successfully with curl: {output_path}")
                        return output_path
                    else:
                        self.logger.error(f"curl download failed: {process.stderr}")
            except Exception as e:
                self.logger.error(f"Error using curl: {e}")
            
            # Пробуем использовать wget
            try:
                self.logger.info("Trying wget for direct download")
                command = [
                    'wget',
                    '-O', output_path,
                    url
                ]
                
                process = subprocess.run(command, capture_output=True, text=True)
                
                if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    self.logger.info(f"Video downloaded successfully with wget: {output_path}")
                    return output_path
                else:
                    self.logger.error(f"wget download failed: {process.stderr}")
            except Exception as e:
                self.logger.error(f"Error using wget: {e}")
            
            # Если все методы не сработали, создаем пустое видео
            self.logger.warning("All download methods failed, creating empty video file")
            return self._create_empty_video(temp_dir)
            
        except Exception as e:
            self.logger.error(f"Alternative download failed: {e}")
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

    def process_video(self, url):
        """Обработка видео"""
        try:
            # Создаем временную директорию для файлов
            temp_dir = os.path.join(self.temp_dir, str(uuid.uuid4()))
            os.makedirs(temp_dir, exist_ok=True)
            
            # Извлекаем ID видео (если это YouTube URL)
            video_id = self._extract_video_id(url) if 'youtube.com' in url or 'youtu.be' in url else None
            
            # Получаем заголовок видео
            if video_id and hasattr(self, 'youtube_api'):
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
                raise ValueError(f"Failed to download video from URL: {url}")
            
            # Извлекаем аудио
            audio_path = self._extract_audio(video_path)
            
            # Если не удалось извлечь аудио, создаем пустой файл
            if not audio_path:
                self.logger.warning("Failed to extract audio, creating empty audio file")
                audio_extractor = AudioExtractor(self.temp_dir)
                audio_path = audio_extractor._create_empty_audio()
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

    def _check_disk_space(self, video_path):
        try:
            video_size = os.path.getsize(video_path)
            required_space = video_size * 3  # 3x размер видео
            
            free_space = shutil.disk_usage(self.temp_dir).free
            if free_space < required_space:
                raise RuntimeError(
                    f"Insufficient disk space. Required: {required_space/1024/1024:.1f}MB, "
                    f"Available: {free_space/1024/1024:.1f}MB"
                )
        except Exception as e:
            logger.error(f"Error checking disk space: {e}")
            raise

    def _cleanup_temp_files(self, temp_files):
        """Очистка временных файлов"""
        for file_path in temp_files:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    self.logger.info(f"Removed temporary file: {file_path}")
            except Exception as e:
                self.logger.error(f"Error removing temp file {file_path}: {e}")

    def _extract_audio(self, video_path):
        """Извлечение аудио из видео в низком качестве"""
        try:
            self.logger.info(f"Extracting audio from video: {video_path}")
            
            # Используем инициализированный экстрактор аудио
            audio_path = self.audio_extractor.extract(video_path)
            self.logger.info(f"Audio extracted to: {audio_path}")
            return audio_path
        except Exception as e:
            self.logger.error(f"Error extracting audio: {e}")
            raise

    def _extract_frames(self, video_path):
        """Извлечение кадров с оптимизацией"""
        try:
            cap = cv2.VideoCapture(video_path)
            frames = []
            
            # Получаем параметры из конфигурации с значениями по умолчанию
            processing_config = self.config.get('processing', {})
            interval = processing_config.get('frame_interval', 30)
            width = processing_config.get('image_max_width', 640)
            quality = processing_config.get('image_quality', 85)
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                    
                # Уменьшаем размер
                height = int(frame.shape[0] * width / frame.shape[1])
                frame = cv2.resize(frame, (width, height))
                
                # Сохраняем с низким качеством
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
                _, buffer = cv2.imencode('.jpg', frame, encode_param)
                frames.append(buffer)
                
                # Пропускаем кадры согласно интервалу
                cap.set(cv2.CAP_PROP_POS_FRAMES, 
                       cap.get(cv2.CAP_PROP_POS_FRAMES) + interval)
            
            cap.release()
            return frames
        except Exception as e:
            self.logger.error(f"Error extracting frames: {e}")
            raise

    def _generate_pdf(self, transcription, frames, video_title):
        """Генерация PDF с текстом и кадрами"""
        try:
            text = transcription
            return self.output_generator.generate(text, frames)
        except Exception as e:
            self.logger.error(f"Error generating PDF: {e}")
            raise

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
        """Загрузка видео с YouTube"""
        try:
            self.logger.info(f"Downloading video from URL: {url}")
            
            # Создаем временную директорию
            temp_dir = os.path.join(self.temp_dir, str(uuid.uuid4()))
            os.makedirs(temp_dir, exist_ok=True)
            
            # Настройки для yt-dlp
            ydl_opts = {
                'format': 'best[height<=720]',  # Ограничиваем качество
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,  # Игнорировать ошибки
            }
            
            # Загружаем видео
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not info:
                        self.logger.warning(f"Could not extract video info from URL: {url}")
                        return self._download_video_alternative(url)
                        
                    video_path = os.path.join(temp_dir, f"{info['title']}.{info['ext']}")
                    
                    # Проверяем, что файл существует и не пустой
                    if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
                        self.logger.warning(f"Downloaded video file not found or empty: {video_path}")
                        return self._download_video_alternative(url)
                        
                    # Проверяем, что файл можно открыть с помощью OpenCV
                    cap = cv2.VideoCapture(video_path)
                    if not cap.isOpened():
                        self.logger.warning(f"Downloaded video cannot be opened: {video_path}")
                        cap.release()
                        return self._download_video_alternative(url)
                    cap.release()
                    
                    self.logger.info(f"Video downloaded successfully: {video_path}")
                    return video_path
            except Exception as e:
                self.logger.error(f"Error downloading video with yt-dlp: {e}")
                return self._download_video_alternative(url)
                
        except Exception as e:
            self.logger.error(f"Error downloading video: {e}")
            # Пробуем альтернативный метод загрузки
            return self._download_video_alternative(url)

def extract_audio(video_path, config):
    """Извлечение аудио из видео"""
    try:
        audio_extractor = AudioExtractor(config['temp_dir'])
        return audio_extractor.extract(video_path)
    except Exception as e:
        logger.error(f"Error extracting audio: {e}")
        return None

def transcribe_audio(audio_path, config):
    """Транскрибация аудио"""
    try:
        model_name = config['transcription']['model']
        use_gpu = config['transcription'].get('use_gpu', False)
        device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
        
        model = WhisperModelCache.get_model(model_name, device)
        result = model.transcribe(audio_path)
        
        return result['segments']
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        return None

def extract_frames(video_path, config):
    """Извлечение и обработка кадров"""
    try:
        frame_processor = FrameProcessor(
            config['output_dir'],
            max_frames=config['video_processing']['max_frames']
        )
        return frame_processor.process(video_path)
    except Exception as e:
        logger.error(f"Error extracting frames: {e}")
        return None

if __name__ == "__main__":
    if len(sys.argv) != 2:
        logger.error("Usage: python process_video.py <video_path>")
        sys.exit(1)
    
    try:
        video_path = sys.argv[1]
        processor = VideoProcessor(config)  # Используем класс напрямую
        result = processor.process_video(video_path)
        logger.info(f"Processing completed successfully! Result: {result}")
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        sys.exit(1)