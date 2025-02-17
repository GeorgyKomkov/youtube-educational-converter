import os
import sys
import logging
import torch
from os import statvfs
from src.audio_extractor import AudioExtractor
from src.frame_processor import FrameProcessor
from src.output_generator import OutputGenerator
import yaml
import whisper
import logging.config
import shutil

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
        try:
            if cls._model is None:
                cls._model = whisper.load_model(model_name, device=device)
            return cls._model
        except Exception as e:
            logger.error(f"Error loading Whisper model: {e}")
            raise

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

def process_video(video_path, output_dir=None):
    """
    Обработка видео: извлечение аудио, транскрибация и создание PDF
    
    Args:
        video_path (str): Путь к видеофайлу
        output_dir (str, optional): Директория для выходных файлов
        
    Returns:
        str: Путь к созданному PDF файлу
    """
    try:
        # Проверка входных данных
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
            
        output_dir = output_dir or config['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        
        # Проверка места на диске
        check_disk_space(output_dir)
        
        # Извлечение аудио
        audio_path = extract_audio(video_path, config)
        if not audio_path:
            raise RuntimeError("Failed to extract audio")
            
        # Транскрибация
        transcription = transcribe_audio(audio_path, config)
        if not transcription:
            raise RuntimeError("Failed to transcribe audio")
            
        # Извлечение кадров
        frames = extract_frames(video_path, config)
        if not frames:
            raise RuntimeError("Failed to extract frames")
            
        # Генерация PDF
        output_generator = OutputGenerator(output_dir)
        result = output_generator.generate({
            'title': os.path.splitext(os.path.basename(video_path))[0],
            'segments': transcription,
            'frames': frames
        })
        
        return result['pdf']
        
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        raise
    finally:
        # Очистка временных файлов
        cleanup_temp(config['temp_dir'])

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
        pdf_path = process_video(video_path)
        logger.info(f"Processing completed successfully! Output: {pdf_path}")
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        sys.exit(1)