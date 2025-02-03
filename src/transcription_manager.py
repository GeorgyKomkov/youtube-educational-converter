import torch
import whisper
import logging

class TranscriptionManager:
    def __init__(self, use_gpu=True, model_size='medium'):
        self.use_gpu = use_gpu and torch.cuda.is_available()
        self.model_size = model_size
        self.logger = logging.getLogger(__name__)

    def transcribe(self, audio_path):
        try:
            # Выбор устройства
            device = 'cuda' if self.use_gpu else 'cpu'
            self.logger.info(f"Транскрибация на устройстве: {device}")
            
            # Загрузка модели
            model = whisper.load_model(self.model_size, device=device)
            
            # Транскрибация
            result = model.transcribe(
                audio_path, 
                verbose=False
            )
            
            # Обработка сегментов
            segments = self._process_segments(result['segments'])
            
            if not segments:
                self.logger.warning("Транскрипция не выявила текстовых сегментов")
            
            self.logger.info(f"Транскрибация завершена. Сегментов: {len(segments)}")
            return segments
        
        except Exception as e:
            self.logger.error(f"Ошибка транскрибации: {e}")
            raise

    def _process_segments(self, segments, min_duration=2.0):
        """Объединение коротких сегментов"""
        processed = []
        current = None
        
        for seg in segments:
            if not current:
                current = seg.copy()
                continue
                
            time_gap = seg['start'] - current['end']
            if time_gap < min_duration:
                current['text'] += ' ' + seg['text'].strip()
                current['end'] = seg['end']
            else:
                processed.append(current)
                current = seg.copy()
                
        if current:
            processed.append(current)
            
        return processed