import cv2
import os
import logging
import numpy as np
from PIL import Image
import torch
from transformers import pipeline
import time
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import yaml
from pathlib import Path

class FrameProcessor:
    def __init__(self, output_dir, max_frames=20, mode='scenes', 
                 blip_enabled=True, max_caption_length=50):
        self.output_dir = Path(output_dir)
        self.max_frames = max_frames
        self.mode = mode
        self.blip_enabled = blip_enabled
        self.max_caption_length = max_caption_length
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config()
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Создание директорий
        self.screenshots_dir = self.output_dir / 'screenshots'
        self.screenshots_dir.mkdir(exist_ok=True)
        
        # Инициализация моделей
        self._initialize_models()
        
        # Добавляем CLIP для лучшего сопоставления текста и изображений
        self.clip_model = self._initialize_clip()

    def _load_config(self):
        """Загрузка конфигурации"""
        try:
            config_path = Path('config/config.yaml')
            if not config_path.exists():
                raise FileNotFoundError("Config file not found")
                
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            return config.get('video_processing', {})
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {}

    def _initialize_models(self):
        """Инициализация ML моделей"""
        try:
            if self.blip_enabled:
                self.caption_model = pipeline(
                    "image-to-text", 
                    model="Salesforce/blip-image-captioning-base",
                    device=self.device
                )
            
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            self.embedding_model.to(self.device)
            
        except Exception as e:
            self.logger.error(f"Error initializing models: {e}")
            raise

    def _initialize_clip(self):
        """Инициализация CLIP модели"""
        try:
            import clip
            model, preprocess = clip.load("ViT-B/32", device=self.device)
            return {"model": model, "preprocess": preprocess}
        except Exception as e:
            self.logger.error(f"Error loading CLIP: {e}")
            raise

    def process(self, video_path):
        """Обработка видео и извлечение кадров"""
        frames = []
        cap = None
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise RuntimeError("Error opening video file")

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            
            frame_indices = self._get_frame_indices(total_frames, fps)
            
            for frame_idx in frame_indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()
                
                if not ret:
                    continue
                    
                try:
                    processed_frame = self._process_frame(frame, frame_idx)
                    if processed_frame:
                        frames.append(processed_frame)
                except Exception as e:
                    self.logger.error(f"Error processing frame {frame_idx}: {e}")
                    continue

            return self._select_most_relevant_frames(frames)
            
        except Exception as e:
            self.logger.error(f"Error processing video: {e}")
            raise
        finally:
            if cap is not None:
                cap.release()

    def _process_frame(self, frame, frame_idx):
        """Обработка отдельного кадра"""
        try:
            # Конвертация BGR в RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame_rgb)
            
            # Сохранение кадра
            output_path = self.screenshots_dir / f"frame_{frame_idx}.jpg"
            image.save(output_path, quality=85)
            
            # Генерация описания если включено
            caption = ""
            if self.blip_enabled:
                caption = self._generate_caption(image)
            
            # Получение эмбеддинга
            embedding = self._get_embedding(caption if caption else "")
            
            return {
                'path': str(output_path),
                'index': frame_idx,
                'caption': caption,
                'embedding': embedding
            }
            
        except Exception as e:
            self.logger.error(f"Error processing frame: {e}")
            return None

    def cleanup(self):
        """Очистка ресурсов"""
        try:
            if hasattr(self, 'caption_model'):
                del self.caption_model
            if hasattr(self, 'embedding_model'):
                del self.embedding_model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def __del__(self):
        """Деструктор для очистки ресурсов"""
        self.cleanup()

    def _select_most_relevant_frames(self, frames, text_segments):
        """Выбор наиболее релевантных кадров для текста"""
        try:
            # Получаем эмбеддинги текста через CLIP
            text_features = self.clip_model["model"].encode_text(text_segments)
            
            # Получаем эмбеддинги изображений
            image_features = []
            for frame in frames:
                image = self.clip_model["preprocess"](Image.open(frame['path']))
                image_features.append(
                    self.clip_model["model"].encode_image(image.unsqueeze(0))
                )
            
            # Вычисляем similarity scores
            similarity = torch.cosine_similarity(
                text_features.unsqueeze(1),
                torch.cat(image_features).unsqueeze(0),
                dim=-1
            )
            
            # Выбираем лучшие кадры для каждого сегмента текста
            best_frames = []
            for scores in similarity:
                best_idx = scores.argmax().item()
                best_frames.append(frames[best_idx])
            
            return best_frames
            
        except Exception as e:
            self.logger.error(f"Error selecting relevant frames: {e}")
            raise