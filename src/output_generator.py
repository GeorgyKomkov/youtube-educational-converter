import os
import logging
import markdown2
import pdfkit
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import shutil

class OutputGenerator:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)
        self.text_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.config = self._load_config()
        self._check_dependencies()
        os.makedirs(output_dir, exist_ok=True)
        if not shutil.which('wkhtmltopdf'):
            raise RuntimeError("wkhtmltopdf не установлен")

    def generate(self, data):
        """Создаёт Markdown и PDF-файл на основе транскрибации и ключевых кадров"""
        try:
            # Проверка свободного места
            free_space = shutil.disk_usage(self.output_dir).free / (1024 * 1024)  # MB
            if free_space < 100:  # Минимум 100MB
                raise RuntimeError(f"Недостаточно места на диске: {free_space}MB")
            
            content = self._prepare_content(data)
            md_path = self._generate_markdown(content)
            pdf_path = self._generate_pdf(md_path)
            return {"markdown": md_path, "pdf": pdf_path}
        except Exception as e:
            self.logger.error(f"Ошибка генерации выходного файла: {e}")
            raise

    def _prepare_content(self, data):
        """Связывает текстовые сегменты с изображениями по смыслу"""
        text_embeddings = self.text_model.encode([s['text'] for s in data['segments']])
        frame_embeddings = [f['embedding'] for f in data['frames']]
        
        similarity_matrix = cosine_similarity(text_embeddings, frame_embeddings)
        
        sections = []
        for i, segment in enumerate(data['segments']):
            best_frame_idx = np.argmax(similarity_matrix[i])
            best_frame = data['frames'][best_frame_idx]
            
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
        """Создаёт Markdown-файл"""
        output_path = os.path.join(self.output_dir, f"{content['title']}.md")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# {content['title']}\n\n")
            for section in content['sections']:
                f.write(f"## Время: {section['time']:.1f} сек\n")
                f.write(f"![{section['frame']['description']}]({section['frame']['path']})\n")
                f.write(f"{section['text']}\n\n")
        
        return output_path

    def _generate_pdf(self, md_path):
        """Конвертирует Markdown в PDF"""
        try:
            options = {
                'page-size': 'A4',
                'margin-top': '20mm',
                'margin-right': '20mm',
                'margin-bottom': '20mm',
                'margin-left': '20mm',
                'encoding': 'UTF-8'
            }
            
            html = markdown2.markdown_path(md_path)
            pdf_path = md_path.replace('.md', '.pdf')
            pdfkit.from_string(html, pdf_path, options=options)
            
            # Проверка размера файла
            if os.path.getsize(pdf_path) > self.config['pdf']['max_size'] * 1024 * 1024:
                raise ValueError("PDF файл слишком большой")
                
            return pdf_path
        finally:
            # Очистка временных файлов
            if os.path.exists(md_path):
                os.remove(md_path)
