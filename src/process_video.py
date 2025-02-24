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
        self.config = config
        self.temp_dir = Path(config['temp_dir'])
        self.temp_dir.mkdir(exist_ok=True)
        try:
            # Создаем временные директории если их нет
            output_dir = self.config.get('output_dir', '/app/output')
            
            # Создаем директории с правильными правами
            os.makedirs(output_dir, exist_ok=True)
            os.chmod(output_dir, 0o777)
            
            logger.info(f"Directories created/checked: temp_dir={self.temp_dir}, output_dir={output_dir}")
            
            # Инициализация модели
            model_name = self.config.get('transcription', {}).get('model', 'tiny')
            logger.info(f"Loading whisper model: {model_name}")
            
            self.whisper_model = load_model(
                name=model_name,
                device="cuda" if torch.cuda.is_available() else "cpu"
            )
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to initialize VideoProcessor: {e}")
            raise RuntimeError(f"Initialization failed: {e}")

    def download_video(self, video_url):
        """Download video from YouTube"""
        try:
            ydl_opts = {
                'format': 'best',
                'outtmpl': str(self.temp_dir / '%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                # Добавляем настройки для обхода ограничений
                'nocheckcertificate': True,
                'ignoreerrors': True,
                'extract_flat': False,
                # Добавляем User-Agent
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            }
            
            logger.info(f"Downloading video from URL: {video_url}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                video_path = self.temp_dir / f"{info['id']}.{info['ext']}"
                logger.info(f"Video downloaded successfully to: {video_path}")
                return str(video_path)
                
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            # Добавляем больше информации об ошибке
            if hasattr(e, 'msg'):
                logger.error(f"Error message: {e.msg}")
            raise RuntimeError(f"Failed to download video: {str(e)}")

    def transcribe_audio(self, audio_path):
        try:
            logger.info(f"Starting transcription of {audio_path}")
            # Загружаем аудио через whisper
            audio = whisper.load_audio(audio_path)
            # Транскрибируем
            result = self.whisper_model.transcribe(audio)
            logger.info("Transcription completed successfully")
            return result["text"]
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            raise RuntimeError(f"Failed to transcribe audio: {e}")

    def process_video(self, video_url, progress_callback=None):
        try:
            # Download video first
            video_path = self.download_video(video_url)
            logger.info(f"Video downloaded to: {video_path}")

            # Process the downloaded video
            audio_path = extract_audio(video_path, self.config)
            if not audio_path:
                raise RuntimeError("Failed to extract audio")

            # Начальный прогресс
            if progress_callback:
                progress_callback(0)
            
            # Проверка и корректировка URL
            if not video_url.startswith('https://'):
                if video_url.startswith('https:/'):
                    video_url = video_url.replace('https:/', 'https://')
                else:
                    video_url = f'https://{video_url.lstrip("/")}' 
                
            logger.info(f"Processing video URL: {video_url}")
            
            # Проверяем и логируем состояние директорий
            logger.info(f"Checking temp directory: {self.temp_dir}")
            logger.info(f"Temp directory exists: {os.path.exists(self.temp_dir)}")
            logger.info(f"Temp directory permissions: {oct(os.stat(self.temp_dir).st_mode)[-3:]}")
            
            # Обработка чанками
            def process_in_chunks(audio_path, chunk_size=30):
                logger.info(f"Processing audio in chunks: {audio_path}")
                results = []
                audio = whisper.load_audio(audio_path)
                
                for i in range(0, len(audio), chunk_size * 16000):
                    chunk = audio[i:i + chunk_size * 16000]
                    logger.info(f"Processing chunk {i//16000}-{(i + chunk_size)//16000} seconds")
                    result = self.whisper_model.transcribe(chunk)
                    results.append(result['text'])
                    
                    # Очистка памяти
                    torch.cuda.empty_cache()
                    gc.collect()
                    
                return " ".join(results)
                
            result = process_in_chunks(audio_path)
            
            # Обновляем прогресс
            if progress_callback:
                progress_callback(100)
            
            return {
                'status': 'success',
                'result': result
            }
        except Exception as e:
            logger.exception(f"Error processing video: {e}")
            raise

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
        for file_path in temp_files:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Error removing temp file {file_path}: {e}")

    def _extract_audio(self, video_path):
        """Извлечение аудио из видео в низком качестве"""
        try:
            return self.audio_extractor.extract(
                video_path, 
                quality='low',
                sample_rate=16000
            )
        except Exception as e:
            self.logger.error(f"Error extracting audio: {e}")
            raise

    def _extract_frames(self, video_path):
        """Извлечение кадров с оптимизацией"""
        try:
            cap = cv2.VideoCapture(video_path)
            frames = []
            interval = self.config['processing']['frame_interval']
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                    
                # Уменьшаем размер
                width = self.config['processing']['image_max_width']
                height = int(frame.shape[0] * width / frame.shape[1])
                frame = cv2.resize(frame, (width, height))
                
                # Сохраняем с низким качеством
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 
                              self.config['processing']['image_quality']]
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

    def _generate_pdf(self, segments, frames):
        """Генерация PDF с текстом и кадрами"""
        try:
            text = ' '.join([segment['text'] for segment in segments])
            return self.output_generator.generate(text, frames)
        except Exception as e:
            self.logger.error(f"Error generating PDF: {e}")
            raise

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
        pdf_path = processor.process_video(video_path)
        logger.info(f"Processing completed successfully! Output: {pdf_path}")
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        sys.exit(1)