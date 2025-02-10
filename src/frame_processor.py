import cv2
import os
import logging
import numpy as np
from PIL import Image
import torch
import torchvision.models as models
import torchvision.transforms as transforms
from transformers import pipeline

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
            self.caption_model = pipeline(
                "image-to-text", 
                model="Salesforce/blip-image-captioning-base",
                device="cuda" if torch.cuda.is_available() else "cpu"
            )
        
        # Модель для эмбеддингов
        self.embedding_model = models.resnet50(pretrained=True)
        self.embedding_model.eval()
        self.transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

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
        """Получение эмбеддинга изображения"""
        try:
            # Преобразование PIL-изображения 
            input_tensor = self.transform(image).unsqueeze(0)
            
            with torch.no_grad():
                features = self.embedding_model(input_tensor)
                embedding = features.squeeze().numpy()
            
            return embedding
        except Exception as e:
            self.logger.warning(f"Ошибка получения эмбеддинга: {e}")
            return None

    def _save_frame(self, image, timestamp):
        filename = os.path.join(
            self.output_dir, 
            'screenshots', 
            f'frame_{timestamp:.2f}.jpg'
        )
        image.save(filename)
        return filename

    def _detect_scene_changes(self, total_frames, fps):
        # Простая реализация обнаружения смены сцен
        return list(range(0, total_frames, int(fps * 10)))

    def _select_most_relevant_frames(self, frames):
        # Алгоритм выбора наиболее уникальных кадров
        return frames[:self.max_frames]