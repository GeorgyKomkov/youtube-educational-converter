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

# Настройка логирования
def setup_logging():
    try:
        with open('config/logging.yaml', 'r') as f:
            config = yaml.safe_load(f)
        logging.config.dictConfig(config)
    except Exception as e:
        # Если не удалось загрузить конфиг, используем базовую настройку
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

# Инициализация логгера
setup_logging()
logger = logging.getLogger(__name__)

# Глобальная конфигурация
config = None

def init_config():
    """Инициализация глобальной конфигурации"""
    global config
    config = load_config()

def load_config():
    """Загрузка конфигурации из YAML файла"""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.yaml')
    if not os.path.exists(config_path):
        logger.warning(f"Файл конфигурации {config_path} не найден, используем значения по умолчанию")
        return {
            'temp_dir': 'temp',
            'output_dir': 'output',
            'transcription': {'model': 'base', 'use_gpu': False},
            'video_processing': {'max_frames': 20, 'frame_mode': 'interval', 'frame_interval': 30},
            'blip': {'enabled': False},
            'memory': {'max_video_size': 100}
        }
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def check_disk_space(path, required_mb=1000):
    """Проверка свободного места на диске"""
    stats = statvfs(path)
    free_mb = (stats.f_bavail * stats.f_frsize) / (1024 * 1024)
    if free_mb < required_mb:
        raise RuntimeError(f"Недостаточно места на диске. Требуется {required_mb}MB, доступно {free_mb}MB")

class WhisperModelCache:
    _instance = None
    
    @classmethod
    def get_model(cls, model_name, device):
        if cls._instance is None:
            cls._instance = whisper.load_model(model_name, device=device)
        return cls._instance

def cleanup_temp(temp_dir):
    """Немедленная очистка временных файлов"""
    try:
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
    except Exception as e:
        logger.error(f"Ошибка очистки: {e}")

def process_video(video_path):
    try:
        temp_dir = "/app/temp"
        # Инициализация с temp_dir
        audio_extractor = AudioExtractor(temp_dir)
        frame_processor = FrameProcessor()
        output_generator = OutputGenerator()

        # Извлечение аудио
        audio_path = audio_extractor.extract(video_path)
        
        # Обработка кадров
        frames = frame_processor.process(video_path)
        
        # Генерация выходного файла
        output_path = output_generator.generate(audio_path, frames)
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error processing video: {e}")
        raise

def extract_audio(video_path, config):
    """Извлечение аудио из видео"""
    audio_extractor = AudioExtractor(config['temp_dir'])
    return audio_extractor.extract(video_path)

def transcribe_audio(audio_path, config):
    """Транскрибация аудио"""
    model_name = config['transcription']['model']
    use_gpu = config['transcription'].get('use_gpu', False)
    device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
    model = WhisperModelCache.get_model(model_name, device)
    result = model.transcribe(audio_path)
    return result['segments']

def extract_frames(video_path, config):
    """
    Извлечение и обработка кадров из видео
    
    Args:
        video_path (str): Путь к видеофайлу
        config (dict): Конфигурация
        
    Returns:
        list: Список обработанных кадров
    """
    try:
        frame_processor = FrameProcessor(
            config['output_dir'],
            max_frames=config['video_processing']['max_frames'],
            mode=config['video_processing']['frame_mode'],
            blip_enabled=config['blip']['enabled']
        )
        
        # Проверяем размер видео
        video_size = os.path.getsize(video_path) / (1024 * 1024)  # MB
        if video_size > config['memory']['max_video_size']:
            raise ValueError(f"Видео слишком большое: {video_size}MB")
        
        # Извлекаем и обрабатываем кадры
        frames = frame_processor.process(video_path)
        
        # Проверяем результат
        if not frames:
            raise ValueError("Не удалось извлечь кадры из видео")
            
        logger.info(f"Успешно извлечено {len(frames)} кадров")
        return frames
        
    except Exception as e:
        logger.error(f"Ошибка при извлечении кадров: {e}")
        raise

def generate_pdf(transcription, frames, video_path, config):
    """Генерация PDF документа"""
    title = os.path.splitext(os.path.basename(video_path))[0]
    data = {
        'title': title,
        'segments': transcription,
        'frames': frames
    }
    output_generator = OutputGenerator(config['output_dir'])
    return output_generator.generate(data)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Необходимо указать путь к видеофайлу в качестве аргумента")
        sys.exit(1)
    
    video_path = sys.argv[1]
    pdf_path = process_video(video_path)
    
    if pdf_path:
        logger.info(f"Обработка видео завершена успешно! Результат: {pdf_path}")
    else:
        logger.error("Обработка видео завершилась с ошибками")
        sys.exit(1)