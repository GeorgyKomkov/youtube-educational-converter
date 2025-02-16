import os
import sys
import logging
import torch
from audio_extractor import AudioExtractor
from frame_processor import FrameProcessor
from output_generator import OutputGenerator
import yaml
import whisper

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    """Загрузка конфигурации из YAML файла"""
    config_path = os.path.join('config', 'config.yaml')
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

def process_video(video_path):
    """Основная функция обработки видео"""
    if not os.path.exists(video_path):
        logger.error(f"Видеофайл не найден: {video_path}")
        return False
    
    try:
        # Загрузка конфигурации
        config = load_config()
        
        # Создание необходимых директорий
        os.makedirs(config['temp_dir'], exist_ok=True)
        os.makedirs(config['output_dir'], exist_ok=True)
        
        # 1. Извлечение аудио из видео
        logger.info("Извлечение аудио...")
        audio_extractor = AudioExtractor(config['temp_dir'])
        audio_path = audio_extractor.extract(video_path)
        
        # 2. Обработка кадров
        logger.info("Обработка видеокадров...")
        frame_processor = FrameProcessor(
            config['output_dir'],
            max_frames=config['video_processing']['max_frames'],
            mode=config['video_processing']['frame_mode'],
            blip_enabled=config['blip']['enabled']
        )
        frames = frame_processor.process(video_path)
        
        # 3. Транскрибация аудио с помощью Whisper
        logger.info("Транскрибация аудио с помощью Whisper...")
        model_name = config['transcription']['model']
        use_gpu = config['transcription'].get('use_gpu', False)
        
        device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
        model = whisper.load_model(model_name, device=device)
        
        result = model.transcribe(audio_path)
        segments = result['segments']
        
        # 4. Генерация выходных файлов
        logger.info("Генерация итоговых документов...")
        title = os.path.splitext(os.path.basename(video_path))[0]
        
        data = {
            'title': title,
            'segments': segments,
            'frames': frames
        }
        
        output_generator = OutputGenerator(config['output_dir'])
        output_files = output_generator.generate(data)
        
        logger.info(f"Обработка завершена успешно! Результаты: {output_files}")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при обработке видео: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logger.error("Необходимо указать путь к видеофайлу в качестве аргумента")
        sys.exit(1)
    
    video_path = sys.argv[1]
    success = process_video(video_path)
    
    if not success:
        logger.error("Обработка видео завершилась с ошибками")
        sys.exit(1)