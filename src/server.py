from flask import Flask, request, jsonify, render_template_string, send_file, redirect, session, url_for
import os
import secrets
import threading
from youtube_api import YouTubeAPI
from datetime import datetime

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Для управления сессиями

VIDEO_DIR = "/app/videos"
OUTPUT_DIR = "/app/output"
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 🔹 HTML-страница
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Video Downloader</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .alert { padding: 10px; margin-bottom: 15px; border-radius: 4px; }
        .error { background-color: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
        .success { background-color: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
        input[type="text"] { width: 100%; padding: 8px; margin: 10px 0; }
        button { padding: 8px 16px; background: #007bff; color: white; border: none; cursor: pointer; }
        button:hover { background: #0056b3; }
    </style>
</head>
<body>
    <h2>YouTube Video Downloader</h2>
    
    {% if error_message %}
    <div class="alert error">{{ error_message }}</div>
    {% endif %}
    
    {% if success_message %}
    <div class="alert success">{{ success_message }}</div>
    {% endif %}
    
    <h3>Введите ссылку на YouTube</h3>
    <form action="/download" method="post">
        <input type="text" name="url" placeholder="https://www.youtube.com/watch?v=..." required>
        <button type="submit">Получить ссылку</button>
    </form>

    {% if download_url %}
        <h3>Ваша ссылка на скачивание:</h3>
        <a href="{{ download_url }}" target="_blank">{{ download_url }}</a>
    {% endif %}
</body>
</html>
"""

youtube_api = YouTubeAPI()

@app.route("/", methods=["GET"])
def index():
    # Получаем сообщения из сессии
    error_message = session.pop('error_message', None)
    success_message = session.pop('success_message', None)
    download_url = session.pop('download_url', None)
    
    return render_template_string(HTML_PAGE, 
                                 download_url=download_url,
                                 error_message=error_message,
                                 success_message=success_message)

@app.route('/auth')
def auth():
    """Инициирует OAuth2 аутентификацию"""
    try:
        youtube_api.authenticate()
        return redirect(url_for('index'))
    except Exception as e:
        session['error_message'] = f"Ошибка аутентификации: {str(e)}"
        return redirect(url_for('index'))

@app.route("/download", methods=["POST"])
def download_video():
    video_url = request.form.get("url") or request.json.get("url")
    
    if not video_url:
        return jsonify({"error": "URL обязателен"}), 400

    try:
        video_id = video_url.split("v=")[-1]
        download_url, title = youtube_api.get_download_url(video_id)

        if not download_url:
            session['error_message'] = "Не удалось получить ссылку на видео"
            return redirect(url_for('index'))

        session['success_message'] = f"Видео '{title}' доступно для скачивания!"
        session['download_url'] = download_url
        return redirect(url_for('index'))
    except Exception as e:
        session['error_message'] = f"Ошибка: {str(e)}"
        return redirect(url_for('index'))

@app.route("/health")
def health_check():
    """Эндпоинт для проверки работоспособности сервера"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
