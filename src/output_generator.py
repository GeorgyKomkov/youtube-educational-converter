import os
import logging
import markdown2
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize
from sentence_transformers import SentenceTransformer

class OutputGenerator:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)
        self.text_model = SentenceTransformer('all-MiniLM-L6-v2')
        os.makedirs(output_dir, exist_ok=True)

    def generate(self, data):
        try:
            content = self._prepare_content(data)
            output_path = self._generate_markdown(content)
            return output_path
        except Exception as e:
            self.logger.error(f"Ошибка генерации: {e}")
            raise

    def _prepare_content(self, data):
        # Кодирование текстовых и графических эмбеддингов
        text_embeddings = self.text_model.encode([s['text'] for s in data['segments']])
        frame_embeddings = [f['embedding'] for f in data['frames'] if f['embedding'] is not None]
        
        # Нормализация эмбеддингов
        text_embeddings = normalize(text_embeddings)
        frame_embeddings = normalize(frame_embeddings)
        
        # Безопасное сравнение с учетом количества эмбеддингов
        if not frame_embeddings:
            frame_embeddings = np.zeros((1, text_embeddings.shape[1]))
        
        similarity_matrix = cosine_similarity(text_embeddings, frame_embeddings)
        
        sections = []
        for i, segment in enumerate(data['segments']):
            if frame_embeddings.size > 0:
                best_frame_idx = np.argmax(similarity_matrix[i])
                best_frame = data['frames'][best_frame_idx]
            else:
                best_frame = data['frames'][0] if data['frames'] else None
            
            sections.append({
                'text': segment['text'],
                'time': segment['start'],
                'frame': best_frame
            })
        
        return {
            'title': data['title'],
            'sections': sections
        }

    def _generate_markdown(self, content):
        output_path = os.path.join(self.output_dir, f"{content['title']}.md")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# {content['title']}\n\n")
            for section in content['sections']:
                f.write(f"## Время: {section['time']:.1f} сек\n")
                if section['frame']:
                    f.write(f"![{section['frame']['description']}]({section['frame']['path']})\n")
                f.write(f"{section['text']}\n\n")
        
        return output_path