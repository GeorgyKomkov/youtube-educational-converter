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
from pathlib import Path

class OutputGenerator:
    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)
        self.logger = logging.getLogger(__name__)
        self.text_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.config = self._load_config()
        self._check_dependencies()
        self.output_dir.mkdir(exist_ok=True)

    def _load_config(self):
        """Загрузка конфигурации"""
        try:
            config_path = Path('config/config.yaml')
            if not config_path.exists():
                raise FileNotFoundError("Config file not found")
                
            with open(config_path, 'r') as f:
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
            
        if not shutil.which('gs'):
            raise RuntimeError("ghostscript not installed")

    def generate_output(self, transcription, frames, video_title):
        """Генерация выходного PDF файла"""
        try:
            # Создание временного MD файла
            md_content = self._generate_markdown(transcription, frames, video_title)
            
            # Проверка места на диске
            self._check_disk_space(len(md_content))
            
            # Сохранение MD
            md_path = self.output_dir / f"{video_title}.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            # Конвертация в PDF
            pdf_path = self._generate_pdf(md_path)
            
            # Сжатие PDF если нужно
            if os.path.getsize(pdf_path) > self.config['pdf']['max_size'] * 1024 * 1024:
                pdf_path = self._compress_pdf(pdf_path)
            
            return pdf_path
            
        except Exception as e:
            self.logger.error(f"Error generating output: {e}")
            raise
            
    def _check_disk_space(self, content_size):
        """Проверка свободного места"""
        try:
            # Оценка требуемого места (3x размер контента)
            required_space = content_size * 3
            free_space = shutil.disk_usage(self.output_dir).free
            
            if free_space < required_space:
                raise RuntimeError(
                    f"Insufficient disk space. Required: {required_space/1024/1024:.1f}MB, "
                    f"Available: {free_space/1024/1024:.1f}MB"
                )
        except Exception as e:
            self.logger.error(f"Error checking disk space: {e}")
            raise

    def _generate_pdf(self, md_path):
        """Генерация PDF из Markdown"""
        try:
            options = {
                'encoding': 'UTF-8',
                'page-size': 'A4',
                'margin-top': '20mm',
                'margin-right': '20mm',
                'margin-bottom': '20mm',
                'margin-left': '20mm',
                'image-quality': 85,
                'image-dpi': 150
            }
            
            with open(md_path, 'r', encoding='utf-8') as f:
                html = markdown2.markdown(f.read())
                
            pdf_path = md_path.with_suffix('.pdf')
            pdfkit.from_string(html, str(pdf_path), options=options)
            
            return pdf_path
        except Exception as e:
            self.logger.error(f"Error generating PDF: {e}")
            raise
        finally:
            try:
                md_path.unlink()
            except Exception as e:
                self.logger.warning(f"Failed to remove temporary MD file: {e}")

    def _compress_pdf(self, pdf_path):
        """Сжатие PDF файла"""
        try:
            compressed_path = pdf_path.with_name(f"{pdf_path.stem}_compressed.pdf")
            
            # Используем Ghostscript для сжатия
            cmd = [
                'gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.4',
                '-dPDFSETTINGS=/ebook', '-dNOPAUSE', '-dQUIET', '-dBATCH',
                f'-sOutputFile={compressed_path}', str(pdf_path)
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            if compressed_path.exists():
                pdf_path.unlink()
                compressed_path.rename(pdf_path)
            
            return pdf_path
        except Exception as e:
            self.logger.error(f"Error compressing PDF: {e}")
            return pdf_path

    def cleanup(self):
        """Очистка ресурсов"""
        try:
            if hasattr(self, 'text_model'):
                del self.text_model
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def __del__(self):
        """Деструктор"""
        self.cleanup()

    def _generate_markdown(self, transcription, frames, video_title):
        """Генерация Markdown с улучшенной структурой"""
        try:
            md_content = [f"# {video_title}\n\n"]
            
            # Группируем текст по темам
            segments = self._group_by_topics(transcription)
            
            for topic, text_segments in segments.items():
                md_content.append(f"## {topic}\n\n")
                
                # Находим релевантные кадры для темы
                relevant_frames = self._find_relevant_frames(text_segments, frames)
                
                # Добавляем текст и изображения
                for text, frame in zip(text_segments, relevant_frames):
                    md_content.append(f"{text}\n\n")
                    if frame:
                        md_content.append(
                            f"![{frame['caption']}]({frame['path']})\n\n"
                        )
                        
            return "\n".join(md_content)
            
        except Exception as e:
            self.logger.error(f"Error generating markdown: {e}")
            raise

    def _group_by_topics(self, transcription):
        """Группировка текста по темам используя NLP"""
        try:
            from transformers import pipeline
            
            classifier = pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli"
            )
            
            # Определяем темы
            topics = classifier(
                transcription,
                candidate_labels=["введение", "основная часть", "заключение"]
            )
            
            # Группируем текст
            segments = {}
            for label in topics['labels']:
                segments[label] = []
                
            # ... логика группировки текста ...
            
            return segments
            
        except Exception as e:
            self.logger.error(f"Error grouping topics: {e}")
            raise
