import torch
import whisper
import logging
import numpy as np
from sentence_transformers import SentenceTransformer

class TranscriptionManager:
    def __init__(self, use_gpu=True, model_size='medium'):
        self.use_gpu = use_gpu and torch.cuda.is_available()
        self.model_size = model_size
        self.logger = logging.getLogger(__name__)
        
        # Модель для семантического сравнения
        self.similarity_model = SentenceTransformer('all-MiniLM-L6-v2')

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

    def _process_segments(self, segments, min_duration=2.0, max_gap=5.0):
        """Умное объединение сегментов с учетом смысловой связности"""
        processed = []
        current = None
        
        for seg in segments:
            if not current:
                current = seg.copy()
                continue
            
            time_gap = seg['start'] - current['end']
            similar_context = self._check_semantic_similarity(current['text'], seg['text'])
            
            if time_gap < max_gap and similar_context:
                current['text'] += ' ' + seg['text'].strip()
                current['end'] = seg['end']
            else:
                processed.append(current)
                current = seg.copy()
        
        if current:
            processed.append(current)
            
        return processed

    def _check_semantic_similarity(self, text1, text2):
        """Проверка семантической близости текстов"""
        embeddings = self.similarity_model.encode([text1, text2])
        similarity = np.dot(embeddings[0], embeddings[1]) / (
            np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
        )
        return similarity > 0.7  # Порог семантической близости