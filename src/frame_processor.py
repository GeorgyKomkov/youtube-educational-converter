import cv2
import os
import logging
import numpy as np
from PIL import Image
import torch
from transformers import pipeline
import time
import shutil
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import yaml

class FrameProcessor:
    def __init__(self, output_dir, max_frames=20, mode='scenes', 
                 blip_enabled=True, max_caption_length=50):
        self.output_dir = output_dir
        self.max_frames = max_frames
        self.mode = mode
        self.blip_enabled = blip_enabled
        self.max_caption_length = max_caption_length
        self.logger = logging.getLogger(__name__)
        self.config = self._load_config()
        
        # Создание директорий
        self.screenshots_dir = os.path.join(output_dir, 'screenshots')
        os.makedirs(self.screenshots_dir, exist_ok=True)
        
        # Инициализация моделей
        self._initialize_models()
        
        # Очистка старых файлов при запуске
        self._cleanup_old_files()

    def _load_config(self):
        """Загрузка конфигурации"""
        try:
            with open('config/config.yaml', 'r') as f:
                config = yaml.safe_load(f)
            return config.get('video_processing', {
                'max_frames': 20,
                'frame_mode': 'interval',
                'frame_interval': 60,
                'max_resolution': '720p'
            })
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {
                'max_frames': 20,
                'frame_mode': 'interval',
                'frame_interval': 60,
                'max_resolution': '720p'
            }

    def _initialize_models(self):
        """Инициализация ML моделей"""
        try:
            # Определение устройства
            if torch.cuda.is_available() and not os.environ.get('DISABLE_CUDA'):
                self.device = "cuda"
                gpu_memory = torch.cuda.get_device_properties(0).total_memory
                if gpu_memory < 4 * 1024 * 1024 * 1024:  # Меньше 4GB
                    self.logger.warning("Low GPU memory, switching to CPU")
                    self.device = "cpu"
            else:
                self.device = "cpu"

            # Инициализация BLIP если включено
            if self.blip_enabled:
                self.caption_model = pipeline(
                    "image-to-text",
                    model="Salesforce/blip-image-captioning-base",
                    device=self.device
                )

            # Инициализация модели для эмбеддингов
            self.embedding_model = SentenceTransformer('clip-ViT-B-32', device=self.device)
            
        except Exception as e:
            self.logger.error(f"Error initializing models: {e}")
            raise

    def _cleanup_old_files(self):
        """Очистка старых временных файлов"""
        try:
            for file in os.listdir(self.screenshots_dir):
                file_path = os.path.join(self.screenshots_dir, file)
                if os.path.getctime(file_path) < (time.time() - 86400):  # Старше 24 часов
                    os.remove(file_path)
        except Exception as e:
            self.logger.error(f"Error cleaning old files: {e}")

    def process(self, video_path):
        """Обработка видео и извлечение кадров"""
        try:
            if not os.path.exists(video_path):
                raise FileNotFoundError(f"Video file not found: {video_path}")

            # Открытие видео
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise RuntimeError("Failed to open video file")

            frames = []
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            duration = frame_count / fps

            # Определение интервала между кадрами
            interval = self._calculate_interval(duration)

            current_time = 0
            while current_time < duration:
                cap.set(cv2.CAP_PROP_POS_MSEC, current_time * 1000)
                ret, frame = cap.read()
                
                if not ret:
                    break

                # Обработка кадра
                processed_frame = self._process_frame(frame, current_time)
                if processed_frame:
                    frames.append(processed_frame)

                current_time += interval

            cap.release()

            # Выбор наиболее релевантных кадров
            return self._select_most_relevant_frames(frames)

        except Exception as e:
            self.logger.error(f"Error processing video: {e}")
            raise
        finally:
            if 'cap' in locals():
                cap.release()

    def _calculate_interval(self, duration):
        """Расчет интервала между кадрами"""
        return max(1, duration / (self.max_frames * 2))

    def _process_frame(self, frame, timestamp):
        """Обработка отдельного кадра"""
        try:
            # Сохранение кадра
            frame_path = os.path.join(self.screenshots_dir, f"frame_{timestamp:.1f}.jpg")
            
            # Конвертация BGR в RGB и сохранение через PIL
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame_rgb)
            
            # Изменение размера если нужно
            max_size = (1280, 720)  # 720p
            if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Сохранение с оптимизацией
            image.save(frame_path, 'JPEG', quality=85, optimize=True)
            
            # Получение описания если включено BLIP
            description = ""
            if self.blip_enabled:
                description = self._generate_caption(image)
            
            # Получение эмбеддинга
            embedding = self._get_embedding(image)
            
            return {
                'path': frame_path,
                'time': timestamp,
                'description': description,
                'embedding': embedding
            }
            
        except Exception as e:
            self.logger.error(f"Error processing frame at {timestamp}: {e}")
            return None

    def _generate_caption(self, image):
        """Генерация описания кадра"""
        try:
            if not self.blip_enabled:
                return ""
                
            captions = self.caption_model(image)
            if captions and len(captions) > 0:
                caption = captions[0]['generated_text']
                return caption[:self.max_caption_length]
            return ""
        except Exception as e:
            self.logger.error(f"Error generating caption: {e}")
            return ""

    def _get_embedding(self, image):
        """Получение эмбеддинга для кадра"""
        try:
            embedding = self.embedding_model.encode(
                image, 
                convert_to_tensor=True,
                show_progress_bar=False
            )
            return embedding.cpu().numpy()
        except Exception as e:
            self.logger.error(f"Error getting embedding: {e}")
            return np.zeros(512)

    def _select_most_relevant_frames(self, frames):
        """Выбор наиболее релевантных кадров"""
        try:
            if len(frames) <= self.max_frames:
                return frames
            
            embeddings = np.array([frame['embedding'] for frame in frames])
            similarity_matrix = cosine_similarity(embeddings)
            
            selected_indices = [0]
            while len(selected_indices) < self.max_frames:
                max_similarities = np.max(similarity_matrix[selected_indices][:, :], axis=0)
                remaining_indices = list(set(range(len(frames))) - set(selected_indices))
                next_frame_idx = remaining_indices[np.argmin(max_similarities[remaining_indices])]
                selected_indices.append(next_frame_idx)
            
            selected_indices.sort()
            return [frames[i] for i in selected_indices]
            
        except Exception as e:
            self.logger.error(f"Error selecting frames: {e}")
            return frames[:self.max_frames]

    def cleanup(self):
        """Очистка ресурсов"""
        try:
            # Очистка CUDA кэша если использовался GPU
            if self.device == "cuda":
                torch.cuda.empty_cache()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")