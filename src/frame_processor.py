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

class FrameProcessor:
    def __init__(self, output_dir, max_frames=100, mode='scenes', 
                 blip_enabled=True, max_caption_length=50):
        self.output_dir = output_dir
        self.max_frames = max_frames
        self.mode = mode
        self.blip_enabled = blip_enabled
        self.max_caption_length = max_caption_length
        self.logger = logging.getLogger(__name__)
        
        os.makedirs(os.path.join(output_dir, 'screenshots'), exist_ok=True)
        
        # Инициализация моделей
        self.caption_model = None
        if self.blip_enabled:
            # Проверка доступности CUDA
            try:
                if torch.cuda.is_available() and not os.environ.get('DISABLE_CUDA'):
                    self.device = "cuda"
                    # Проверка памяти GPU
                    gpu_memory = torch.cuda.get_device_properties(0).total_memory
                    if gpu_memory < 4 * 1024 * 1024 * 1024:  # Меньше 4GB
                        self.logger.warning("Недостаточно GPU памяти, переключаемся на CPU")
                        self.device = "cpu"
                else:
                    self.device = "cpu"
            except Exception as e:
                self.logger.warning(f"Ошибка при инициализации CUDA: {e}")
                self.device = "cpu"
            self.caption_model = pipeline(
                "image-to-text", 
                model="Salesforce/blip-image-captioning-base",
                device=self.device
            )
        
        # Добавить загрузку конфигурации
        self.config = self._load_config()
        # Добавить проверку свободного места
        self._check_disk_space()
        
        # Добавить очистку временных файлов
        self._cleanup_old_files()

    def _cleanup_old_files(self):
        """Очистка старых временных файлов"""
        try:
            screenshots_dir = os.path.join(self.output_dir, 'screenshots')
            for file in os.listdir(screenshots_dir):
                file_path = os.path.join(screenshots_dir, file)
                if os.path.getctime(file_path) < (time.time() - 86400):  # Старше 24 часов
                    os.remove(file_path)
        except Exception as e:
            self.logger.warning(f"Ошибка при очистке файлов: {e}")

    def _check_disk_space(self):
        """Проверка свободного места на диске"""
        free_space = shutil.disk_usage(self.output_dir).free / (1024 * 1024)  # MB
        if free_space < self.config['min_free_space']:
            raise RuntimeError(f"Недостаточно места на диске: {free_space}MB")

    def process(self, video_path):
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError("Не удалось открыть видеофайл")
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            frame_indices = self._select_frame_indices(total_frames, fps)
            frames = self._capture_frames(cap, frame_indices, fps)
            
            cap.release()
            
            if len(frames) > self.max_frames:
                frames = self._select_most_relevant_frames(frames)
            
            self.logger.info(f"Обработано кадров: {len(frames)}")
            return frames
        
        except Exception as e:
            self.logger.error(f"Ошибка обработки кадров: {e}")
            raise

    def _select_frame_indices(self, total_frames, fps):
        if self.mode == 'scenes':
            return self._detect_scene_changes(total_frames, fps)
        else:
            interval = int(fps * 30)  # Каждые 30 секунд
            return list(range(0, total_frames, interval))

    def _capture_frames(self, cap, frame_indices, fps):
        frames = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                continue
                
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)
            
            # Генерация описания и семантического эмбеддинга
            description = self._generate_caption(pil_image)
            embedding = self._get_image_embedding(pil_image)
            
            timestamp = idx / fps
            img_path = self._save_frame(pil_image, timestamp)
            
            frames.append({
                'timestamp': timestamp,
                'path': img_path,
                'description': description,
                'embedding': embedding
            })
        return frames

    def _generate_caption(self, image):
        try:
            result = self.caption_model(image)
            caption = result[0]['generated_text']
            return caption[:self.max_caption_length]
        except Exception as e:
            self.logger.warning(f"Ошибка генерации описания: {e}")
            return "Кадр из видео"

    def _get_image_embedding(self, image):
        """
        Получает эмбеддинг изображения используя предобученную модель
        
        Args:
            image (PIL.Image): Входное изображение
            
        Returns:
            numpy.ndarray: Эмбеддинг изображения
        """
        try:
            # Используем ту же модель BLIP для эмбеддингов
            if not hasattr(self, 'embedding_model'):
                self.embedding_model = SentenceTransformer('clip-ViT-B-32')
            
            # Преобразуем изображение в тензор
            image_embedding = self.embedding_model.encode(
                image, 
                convert_to_tensor=True,
                show_progress_bar=False
            )
            
            # Преобразуем в numpy массив для сохранения
            return image_embedding.cpu().numpy()
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении эмбеддинга: {e}")
            # Возвращаем нулевой вектор в случае ошибки
            return np.zeros(512)  # CLIP возвращает 512-мерные векторы

    def _select_most_relevant_frames(self, frames):
        """
        Выбирает наиболее релевантные и разнообразные кадры
        
        Args:
            frames (list): Список кадров с их эмбеддингами
            
        Returns:
            list: Отфильтрованный список кадров
        """
        try:
            if len(frames) <= self.max_frames:
                return frames
            
            # Получаем эмбеддинги всех кадров
            embeddings = np.array([frame['embedding'] for frame in frames])
            
            # Вычисляем матрицу схожести между кадрами
            similarity_matrix = cosine_similarity(embeddings)
            
            # Инициализируем список выбранных кадров первым кадром
            selected_indices = [0]
            
            # Выбираем кадры с наименьшей схожестью с уже выбранными
            while len(selected_indices) < self.max_frames:
                # Вычисляем максимальную схожесть для каждого кадра с выбранными
                max_similarities = np.max(similarity_matrix[selected_indices][:, :], axis=0)
                
                # Выбираем кадр с наименьшей схожестью
                remaining_indices = list(set(range(len(frames))) - set(selected_indices))
                next_frame_idx = remaining_indices[np.argmin(max_similarities[remaining_indices])]
                
                selected_indices.append(next_frame_idx)
            
            # Сортируем по времени
            selected_indices.sort()
            
            self.logger.info(f"Отобрано {len(selected_indices)} кадров из {len(frames)}")
            return [frames[i] for i in selected_indices]
            
        except Exception as e:
            self.logger.error(f"Ошибка при выборе кадров: {e}")
            # В случае ошибки возвращаем первые max_frames кадров
            return frames[:self.max_frames]