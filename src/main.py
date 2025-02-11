from flask import Flask, request, jsonify
from src.video_downloader import VideoDownloader
from src.audio_extractor import AudioExtractor
from src.transcription_manager import TranscriptionManager
from src.frame_processor import FrameProcessor
from src.output_generator import OutputGenerator
from src.video_converter import VideoConverter
import os
import yaml

app = Flask(__name__)

# Загрузка конфигурации из YAML
with open('config/config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# Создание объекта VideoConverter
converter = VideoConverter(config)  # <-- Эта строка обязательна!

# Получаем порт из переменных окружения
PORT = int(os.getenv("PORT", 10000))

# Добавляем HTML форму здесь (ПЕРЕД существующим роутом /convert)
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

# Обработчик конвертации
@app.route('/convert', methods=['POST'])
def convert_video():
    data = request.json
    url = data.get("url")
    if not url:
        return jsonify({"error": "URL is required"}), 400
    
    result = converter.convert(url)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)