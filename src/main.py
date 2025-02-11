from flask import Flask, request, jsonify
from src.video_downloader import VideoDownloader
from src.audio_extractor import AudioExtractor
from src.transcription_manager import TranscriptionManager
from src.frame_processor import FrameProcessor
from src.output_generator import OutputGenerator
import os
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

PORT = int(os.getenv("PORT", 10000))

class VideoConverter:
    def __init__(self, config):
        self.config = config
        self.downloader = VideoDownloader(config['temp_dir'])
        self.audio_extractor = AudioExtractor(config['temp_dir'])
        self.transcriber = TranscriptionManager(config['transcription'])
        self.frame_processor = FrameProcessor(
            config['output_dir'],
            max_frames=config['video_processing']['max_frames'],
            mode=config['video_processing']['frame_mode'],
            blip_enabled=config['blip']['enabled']
        )
        self.output_generator = OutputGenerator(config['output_dir'])

    def convert(self, url):
        try:
            video_path, title = self.downloader.download(url)
            audio_path = self.audio_extractor.extract(video_path)
            
            segments = self.transcriber.transcribe(audio_path)
            frames = self.frame_processor.process(video_path)
            
            result = self.output_generator.generate({
                'title': title,
                'segments': segments,
                'frames': frames
            })
            
            return result
        except Exception as e:
            logger.error(f"Error during conversion: {str(e)}")
            raise

converter = VideoConverter({
    "temp_dir": "temp/",
    "output_dir": "output/",
    "transcription": {"model": "base"},
    "video_processing": {"max_frames": 50, "frame_mode": "interval"},
    "blip": {"enabled": False}
})

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>YouTube Video Converter</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 20px auto;
                padding: 0 20px;
            }
            .form-container {
                background: #f5f5f5;
                padding: 20px;
                border-radius: 5px;
            }
            input[type="text"] {
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            button {
                background: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
            }
            button:hover {
                background: #45a049;
            }
            #result {
                margin-top: 20px;
                padding: 10px;
            }
        </style>
    </head>
    <body>
        <h1>YouTube Video to Educational Textbook Converter</h1>
        <div class="form-container">
            <form id="convertForm">
                <input type="text" id="url" name="url" placeholder="Введите URL видео с YouTube" required>
                <button type="submit">Конвертировать</button>
            </form>
        </div>
        <div id="result"></div>

        <script>
            document.getElementById('convertForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const resultDiv = document.getElementById('result');
                resultDiv.textContent = 'Начинаем конвертацию...';
                
                try {
                    const response = await fetch('/convert', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            url: document.getElementById('url').value
                        })
                    });
                    
                    const data = await response.json();
                    if (response.ok) {
                        resultDiv.textContent = 'Конвертация успешно завершена!';
                    } else {
                        resultDiv.textContent = `Ошибка: ${data.error || 'Что-то пошло не так'}`;
                    }
                } catch (error) {
                    resultDiv.textContent = `Ошибка: ${error.message}`;
                }
            });
        </script>
    </body>
    </html>
    '''

@app.route('/convert', methods=['POST'])
def convert_video():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Invalid JSON data"}), 400
        
        url = data.get("url")
        if not url:
            return jsonify({"error": "URL is required"}), 400
        
        if not url.startswith(('http://', 'https://', 'www.')):
            return jsonify({"error": "Invalid URL format"}), 400
        
        result = converter.convert(url)
        return jsonify({"success": True, "result": result})
    
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.errorhandler(Exception)
def handle_error(e):
    logger.error(f"Unhandled error: {str(e)}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    # Создаем необходимые директории
    os.makedirs("temp", exist_ok=True)
    os.makedirs("output", exist_ok=True)
    
    app.run(host="0.0.0.0", port=PORT, debug=False)