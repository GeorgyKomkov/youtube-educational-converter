import os
import yaml
import logging
from flask import Flask, request, jsonify
from werkzeug.exceptions import HTTPException
from src.video_downloader import VideoDownloader
from src.audio_extractor import AudioExtractor
from src.transcription_manager import TranscriptionManager
from src.frame_processor import FrameProcessor
from src.output_generator import OutputGenerator
from src.video_converter import VideoConverter
from sentence_transformers import SentenceTransformer
import whisper

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ✅ Исправленный путь к `config.yaml`
CONFIG_PATH = "/app/config/config.yaml"

# ✅ Загрузка конфигурации
try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    logger.info("Конфигурация успешно загружена.")
except Exception as e:
    logger.critical(f"Ошибка загрузки конфигурации: {e}")
    config = {}

# ✅ Кешируем модели (Whisper и SentenceTransformer)
logger.info("Загрузка моделей...")
try:
    whisper_model = whisper.load_model(config.get('transcription', {}).get('model', 'base'))
    text_model = SentenceTransformer('all-MiniLM-L6-v2')
    logger.info("Модели успешно загружены.")
except Exception as e:
    logger.critical(f"Ошибка загрузки моделей: {e}")
    whisper_model = None
    text_model = None

# ✅ Создаём объект VideoConverter, передавая кешированные модели
if whisper_model and text_model:
    converter = VideoConverter(config)
else:
    logger.critical("Ошибка: модели не загружены. Конвертация невозможна.")
    converter = None

@app.route('/')
def home():
    return '''
    <html>
    <body>
        <form id="convertForm">
            <input type="text" name="url" placeholder="YouTube URL" required>
            <button type="submit">Convert</button>
        </form>
        <div id="result"></div>

        <script>
            document.getElementById('convertForm').onsubmit = function(e) {
                e.preventDefault();
                
                const url = document.querySelector('input[name="url"]').value;
                
                fetch('/convert', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ url: url })
                })
                .then(response => response.json())
                .then(data => {
                    document.getElementById('result').innerText = JSON.stringify(data, null, 2);
                })
                .catch(error => {
                    document.getElementById('result').innerText = 'Error: ' + error;
                });
            };
        </script>
    </body>
    </html>
    '''

@app.route('/convert', methods=['POST'])
def convert_video():
    try:
        if not converter:
            return jsonify({"error": "Сервер не готов. Модели не загружены."}), 500

        data = request.json
        url = data.get("url")
        if not url:
            return jsonify({"error": "URL is required"}), 400
        
        result = converter.convert(url)
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Ошибка при конвертации: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=False)
