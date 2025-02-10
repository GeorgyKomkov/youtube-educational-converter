import os
import yaml
import logging
from flask import Flask, request, jsonify, render_template
from werkzeug.exceptions import HTTPException

# Импорт всех необходимых классов
from src.video_converter import VideoConverter

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

app = Flask(__name__, 
            template_folder='templates', 
            static_folder='static')

# Загрузка конфигурации
try:
    with open('config/config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
except Exception as e:
    logger.critical(f"Ошибка загрузки конфигурации: {e}")
    config = {}

# Создание объекта VideoConverter
converter = VideoConverter(config)

# Получаем порт из переменных окружения
PORT = int(os.getenv("PORT", 10000))

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_video():
    try:
        data = request.json
        url = data.get("url")
        
        # Валидация URL
        if not url:
            return jsonify({
                "status": "error", 
                "message": "URL является обязательным полем"
            }), 400
        
        # Проверка корректности URL 
        if not url.startswith(('http://', 'https://', 'www.')):
            return jsonify({
                "status": "error", 
                "message": "Некорректный формат URL"
            }), 400
        
        # Конвертация видео
        result = converter.convert(url)
        
        return jsonify({
            "status": "success", 
            "output": result,
            "message": "Видео успешно конвертировано"
        })
    
    except ValueError as ve:
        logger.error(f"Ошибка валидации: {ve}")
        return jsonify({
            "status": "validation_error", 
            "message": str(ve)
        }), 400
    
    except Exception as e:
        logger.error(f"Необработанная ошибка конвертации: {e}")
        return jsonify({
            "status": "error", 
            "message": "Произошла непредвиденная ошибка при конвертации"
        }), 500

@app.route('/status')
def app_status():
    return jsonify({
        "status": "online",
        "components": {
            "video_downloader": True,
            "audio_extractor": True,
            "transcription": config['transcription']['model'],
            "frame_processing": config['video_processing']['max_frames']
        }
    })

# Глобальный обработчик ошибок
@app.errorhandler(Exception)
def handle_exception(e):
    # HTTP-ошибки
    if isinstance(e, HTTPException):
        return jsonify({
            "status": "http_error",
            "message": e.description
        }), e.code
    
    # Все прочие ошибки
    logger.error(f"Критическая ошибка: {e}", exc_info=True)
    return jsonify({
        "status": "critical_error", 
        "message": "Внутренняя ошибка сервера"
    }), 500

if __name__ == "__main__":
    app.run(
        host="0.0.0.0", 
        port=PORT, 
        debug=False
    )