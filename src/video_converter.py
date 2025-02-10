import os
import uuid
import logging
from datetime import datetime

# Импорт всех необходимых классов
from .video_downloader import VideoDownloader
from .audio_extractor import AudioExtractor
from .transcription_manager import TranscriptionManager
from .frame_processor import FrameProcessor
from .output_generator import OutputGenerator

class VideoConverter:
    def __init__(self, config):
        # Настройка логирования
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # Создание уникальной директории для сессии
        self.session_id = str(uuid.uuid4())
        self.session_temp_dir = os.path.join(
            config['temp_dir'], 
            self.session_id
        )
        os.makedirs(self.session_temp_dir, exist_ok=True)
        
        # Инициализация компонентов с расширенной конфигурацией
        self.downloader = VideoDownloader(
            self.session_temp_dir, 
            proxy=config.get('proxy')
        )
        
        self.audio_extractor = AudioExtractor(self.session_temp_dir)
        
        self.transcriber = TranscriptionManager(
            use_gpu=config['transcription']['use_gpu'], 
            model_size=config['transcription']['model']
        )
        
        self.frame_processor = FrameProcessor(
            config['output_dir'],
            max_frames=config['video_processing']['max_frames'],
            mode=config['video_processing']['frame_mode'],
            blip_enabled=config['blip']['enabled']
        )
        
        self.output_generator = OutputGenerator(config['output_dir'])

    def convert(self, url):
        """
        Полный цикл конвертации видео с расширенной обработкой
        """
        start_time = datetime.now()
        video_path = None
        audio_path = None
        
        try:
            # Скачивание видео
            video_path, title = self.downloader.download(url)
            if not video_path:
                raise ValueError("Не удалось скачать видео")
            
            video_size = os.path.getsize(video_path) / (1024 * 1024)  # МБ
            self.logger.info(f"Видео скачано: {title}, размер: {video_size:.2f} МБ")
            
            # Извлечение аудио
            audio_path = self.audio_extractor.extract(video_path)
            if not audio_path:
                raise ValueError("Не удалось извлечь аудио")
            
            audio_size = os.path.getsize(audio_path) / (1024 * 1024)  # МБ
            self.logger.info(f"Аудио извлечено, размер: {audio_size:.2f} МБ")
            
            # Транскрибация
            segments = self.transcriber.transcribe(audio_path)
            if not segments:
                raise ValueError("Транскрипция не дала результатов")
            
            total_text_length = sum(len(seg['text']) for seg in segments)
            self.logger.info(f"Транскрибировано: {len(segments)} сегментов, общая длина: {total_text_length} символов")
            
            # Обработка кадров
            frames = self.frame_processor.process(video_path)
            if not frames:
                raise ValueError("Не удалось обработать кадры")
            
            frame_descriptions = [f['description'] for f in frames]
            self.logger.info(f"Обработано кадров: {len(frames)}")
            
            # Генерация выходных данных
            result = self.output_generator.generate({
                'title': title,
                'segments': segments,
                'frames': frames
            })
            
            # Статистика конвертации
            end_time = datetime.now()
            conversion_time = (end_time - start_time).total_seconds()
            
            self.logger.info(f"Конвертация завершена за {conversion_time:.2f} сек")
            
            return {
                'output_path': result,
                'title': title,
                'segments_count': len(segments),
                'frames_count': len(frames),
                'conversion_time': conversion_time
            }
        
        except Exception as e:
            self.logger.error(f"Ошибка конвертации: {e}", exc_info=True)
            raise
        
        finally:
            # Очистка временных файлов с дополнительной защитой
            def safe_remove(path):
                try:
                    if path and os.path.exists(path):
                        os.remove(path)
                        self.logger.info(f"Временный файл удален: {path}")
                except Exception as e:
                    self.logger.warning(f"Не удалось удалить файл {path}: {e}")
            
            safe_remove(video_path)
            safe_remove(audio_path)
            
            # Попытка удаления временной директории сессии
            try:
                os.rmdir(self.session_temp_dir)
            except Exception as e:
                self.logger.warning(f"Не удалось удалить директорию сессии: {e}")