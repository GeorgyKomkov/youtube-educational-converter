import os
import logging
import markdown2
import pdfkit
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import shutil
import subprocess
from PIL import Image

class OutputGenerator:
    def __init__(self, output_dir):
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)
        self.text_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.config = self._load_config()
        self._check_dependencies()
        os.makedirs(output_dir, exist_ok=True)

    def _load_config(self):
        """Загрузка конфигурации"""
        try:
            with open('config/config.yaml', 'r') as f:
                import yaml
                return yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
            return {
                'pdf': {
                    'template': 'default',
                    'max_size': 50,
                    'compression': 'medium'
                }
            }

    def _check_dependencies(self):
        """Проверка зависимостей"""
        if not shutil.which('wkhtmltopdf'):
            raise RuntimeError("wkhtmltopdf not installed")
            
        try:
            import PIL
            import markdown2
            import pdfkit
        except ImportError as e:
            raise RuntimeError(f"Required package not installed: {e}")

    def generate(self, data):
        """Создание выходных файлов"""
        try:
            # Проверка входных данных
            if not all(key in data for key in ['title', 'segments', 'frames']):
                raise ValueError("Missing required data fields")

            # Подготовка контента
            content = self._prepare_content(data)
            
            # Генерация файлов
            md_path = self._generate_markdown(content)
            pdf_path = self._generate_pdf(md_path)
            
            # Проверка размера PDF
            if os.path.getsize(pdf_path) > self.config['pdf']['max_size'] * 1024 * 1024:
                pdf_path = self._compress_pdf(pdf_path)
            
            return {
                'markdown': md_path,
                'pdf': pdf_path
            }
            
        except Exception as e:
            self.logger.error(f"Error generating output: {e}")
            raise

    def _prepare_content(self, data):
        """Подготовка контента"""
        try:
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
        except Exception as e:
            self.logger.error(f"Error preparing content: {e}")
            raise

    def _generate_markdown(self, content):
        """Создание Markdown файла"""
        try:
            output_path = os.path.join(self.output_dir, f"{content['title']}.md")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# {content['title']}\n\n")
                for section in content['sections']:
                    f.write(f"## Time: {section['time']:.1f} sec\n")
                    f.write(f"![{section['frame']['description']}]({section['frame']['path']})\n")
                    f.write(f"{section['text']}\n\n")
            
            return output_path
        except Exception as e:
            self.logger.error(f"Error generating markdown: {e}")
            raise

    def _generate_pdf(self, md_path):
        """Конвертация в PDF"""
        try:
            options = {
                'page-size': 'A4',
                'margin-top': '20mm',
                'margin-right': '20mm',
                'margin-bottom': '20mm',
                'margin-left': '20mm',
                'encoding': 'UTF-8',
                'image-quality': 85,
                'image-dpi': 150
            }
            
            with open(md_path, 'r', encoding='utf-8') as f:
                html = markdown2.markdown(f.read())
                
            pdf_path = md_path.replace('.md', '.pdf')
            pdfkit.from_string(html, pdf_path, options=options)
            
            return pdf_path
        except Exception as e:
            self.logger.error(f"Error generating PDF: {e}")
            raise
        finally:
            if os.path.exists(md_path):
                os.remove(md_path)

    def _compress_pdf(self, pdf_path):
        """Сжатие PDF файла"""
        try:
            compressed_path = pdf_path.replace('.pdf', '_compressed.pdf')
            
            # Используем Ghostscript для сжатия
            cmd = [
                'gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4',
                '-dPDFSETTINGS=/ebook', '-dNOPAUSE', '-dQUIET', '-dBATCH',
                f'-sOutputFile={compressed_path}', pdf_path
            ]
            
            subprocess.run(cmd, check=True)
            
            if os.path.exists(compressed_path):
                os.remove(pdf_path)
                os.rename(compressed_path, pdf_path)
            
            return pdf_path
        except Exception as e:
            self.logger.error(f"Error compressing PDF: {e}")
            return pdf_path
