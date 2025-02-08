from flask import Flask, request, jsonify
from src.video_downloader import VideoDownloader
from src.audio_extractor import AudioExtractor
from src.transcription_manager import TranscriptionManager
from src.frame_processor import FrameProcessor
from src.output_generator import OutputGenerator
import os

app = Flask(__name__)

# Получаем порт из переменных окружения (Render его задает автоматически)
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

# Создаем объект обработчика
converter = VideoConverter({
    "temp_dir": "temp/",
    "output_dir": "output/",
    "transcription": {"model": "base"},
    "video_processing": {"max_frames": 50, "frame_mode": "interval"},
    "blip": {"enabled": False}
})

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