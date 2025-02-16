import os
import sys
import logging
import torch
from os import statvfs
from audio_extractor import AudioExtractor
from frame_processor import FrameProcessor
from output_generator import OutputGenerator
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
            'blip': {'enabled': False}
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

def process_video(video_path):
    """Основная функция обработки видео"""
    try:
        config = load_config()
        check_disk_space(config['temp_dir'])
        
        # Создаем временные директории
        for dir_path in [config['temp_dir'], config['output_dir']]:
            os.makedirs(dir_path, exist_ok=True)
            
        # Обработка частями
        chunk_size = 1024 * 1024  # 1MB chunks
        with open(video_path, 'rb') as video_file:
            while chunk := video_file.read(chunk_size):
                # Обработка чанка
                pass
                
        # Очистка после каждого этапа
        def cleanup_temp():
            for f in os.listdir(config['temp_dir']):
                os.remove(os.path.join(config['temp_dir'], f))
                
        # 1. Извлечение аудио
        audio_path = extract_audio(video_path)
        
        # 2. Транскрибация
        transcription = transcribe_audio(audio_path)
        cleanup_temp()  # Очищаем аудио
        
        # 3. Извлечение кадров
        frames = extract_frames(video_path)
        cleanup_temp()  # Очищаем временные кадры
        
        # 4. Генерация PDF
        pdf_path = generate_pdf(transcription, frames)
        cleanup_temp()  # Очищаем все временные файлы
        
        return pdf_path
        
    except Exception as e:
        logger.error(f"Ошибка при обработке видео: {e}")
        cleanup_temp()
        return None

def extract_audio(video_path):
    """Извлечение аудио из видео"""
    audio_extractor = AudioExtractor(config['temp_dir'])
    return audio_extractor.extract(video_path)

def transcribe_audio(audio_path):
    """Транскрибация аудио"""
    model_name = config['transcription']['model']
    use_gpu = config['transcription'].get('use_gpu', False)
    device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
    model = WhisperModelCache.get_model(model_name, device)
    result = model.transcribe(audio_path)
    return result['segments']

def extract_frames(video_path):
    """Извлечение кадров из видео"""
    frame_processor = FrameProcessor(
        config['output_dir'],
        max_frames=config['video_processing']['max_frames'],
        mode=config['video_processing']['frame_mode']
    )
    return frame_processor.process(video_path)

def generate_pdf(transcription, frames):
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