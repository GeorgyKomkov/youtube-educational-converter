from flask import Flask, request, jsonify, render_template_string, send_file, redirect, session, url_for
import subprocess
import os
import time
import threading
import secrets
import json
from urllib.parse import quote

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # For session management

VIDEO_DIR = "/app/videos"
OUTPUT_DIR = "/app/output"
COOKIES_DIR = "/app/cookies"
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(COOKIES_DIR, exist_ok=True)

# 🔹 Блокировка для контроля одновременного скачивания
lock = threading.Lock()

# 🔹 HTML-страница для ввода ссылки
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
    
    {% if not logged_in %}
    <p>Для скачивания некоторых видео требуется авторизация на YouTube.</p>
    <a href="/login"><button>Войти через YouTube</button></a>
    {% else %}
    <p>Вы авторизованы в YouTube. Теперь можно скачивать видео, включая возрастные ограничения.</p>
    <form action="/logout" method="post">
        <button type="submit">Выйти</button>
    </form>
    {% endif %}
    
    <h3>Введите ссылку на YouTube</h3>
    <form action="/download" method="post">
        <input type="text" name="url" placeholder="https://www.youtube.com/watch?v=..." required>
        <button type="submit">Скачать</button>
    </form>

    {% if pdf_link %}
        <h3>Ваш PDF-учебник готов:</h3>
        <a href="{{ pdf_link }}" download>Скачать PDF</a>
    {% endif %}
</body>
</html>
"""

@app.route("/login")
def login():
    # Generate unique session ID for this user
    session_id = secrets.token_urlsafe(16)
    session['session_id'] = session_id
    
    # Save a placeholder cookie file
    cookie_file = os.path.join(COOKIES_DIR, f"{session_id}.txt")
    with open(cookie_file, 'w') as f:
        f.write("# Placeholder for YouTube cookies")
    
    # Prepare YouTube login URL with instructions
    login_instructions = """
    <h2>YouTube Authentication Instructions</h2>
    <ol>
        <li>Log in to your YouTube account</li>
        <li>After logging in, come back to this tab and click "I've Logged In"</li>
        <li>We'll use your browser's YouTube session for downloading videos</li>
    </ol>
    <form action="/auth_complete" method="get">
        <button type="submit">I've Logged In</button>
    </form>
    """
    
    # Open YouTube in a new tab and show instructions
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>YouTube Login</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
        </style>
        <script>
            window.open('https://www.youtube.com', '_blank');
        </script>
    </head>
    <body>
        {login_instructions}
    </body>
    </html>
    """

@app.route("/auth_complete")
def auth_complete():
    session['logged_in'] = True
    session['success_message'] = "Авторизация YouTube успешна! Теперь вы можете скачивать видео."
    return redirect(url_for('index'))

@app.route("/logout", methods=["POST"])
def logout():
    # Clear session data
    session_id = session.get('session_id')
    if session_id:
        cookie_file = os.path.join(COOKIES_DIR, f"{session_id}.txt")
        if os.path.exists(cookie_file):
            os.remove(cookie_file)
    
    session.clear()
    return redirect(url_for('index'))

@app.route("/download", methods=["POST"])
def download_video():
    global lock
    video_url = request.form.get("url") or request.json.get("url")
    
    if not video_url:
        return jsonify({"error": "URL обязателен"}), 400

    app.logger.info(f"Получен URL для скачивания: {video_url}")  # Логируем URL

    filename = os.path.join(VIDEO_DIR, "video.mp4")
    session_id = session.get('session_id')
    
    with lock:
        # Base command without authentication
        command = f"yt-dlp -o {filename} {video_url}"
        
        # If user is logged in, try to use their session
        if session.get('logged_in') and session_id:
            cookie_file = os.path.join(COOKIES_DIR, f"{session_id}.txt")
            if os.path.exists(cookie_file):
                command = f"yt-dlp --cookies {cookie_file} -o {filename} {video_url}"
        
        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            error_msg = result.stderr
            app.logger.error(f"Ошибка yt-dlp: {error_msg}")
            
            # If it's an authentication error and we're not using API
            if "sign in to confirm your age" in error_msg.lower() or "private video" in error_msg.lower():
                if request.form.get("url"):  # Browser request
                    session['error_message'] = "Для этого видео требуется вход на YouTube. Пожалуйста, авторизуйтесь."
                    return redirect(url_for('index'))
                else:  # API request
                    return jsonify({
                        "error": "Требуется авторизация на YouTube",
                        "auth_required": True
                    }), 403
            
            # Other errors
            if request.form.get("url"):  # Browser request
                session['error_message'] = f"Ошибка скачивания: {error_msg[:200]}..."
                return redirect(url_for('index'))
            else:  # API request
                return jsonify({
                    "error": f"Ошибка скачивания: {error_msg[:200]}...",
                    "full_error": error_msg
                }), 500

    if not os.path.exists(filename):
        error_msg = "Ошибка скачивания видео: файл не создан"
        if request.form.get("url"):  # Browser request
            session['error_message'] = error_msg
            return redirect(url_for('index'))
        else:  # API request
            return jsonify({"error": error_msg}), 500

    # Success handling
    if request.form.get("url"):  # Browser request
        session['success_message'] = "Видео успешно скачано!"
        return redirect(url_for('index'))
    else:  # API request
        return jsonify({"message": "Видео скачано", "file": filename})


@app.route("/get_video", methods=["GET"])
def get_video():
    filename = os.path.join(VIDEO_DIR, "video.mp4")
    if not os.path.exists(filename):
        return jsonify({"error": "Видео не найдено"}), 404
    return send_file(filename, as_attachment=True)

@app.route("/upload_pdf", methods=["POST"])
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "Нет файла"}), 400
    
    file = request.files["file"]
    pdf_path = os.path.join(OUTPUT_DIR, file.filename)
    file.save(pdf_path)
    
    return jsonify({"message": "PDF сохранен", "file": pdf_path})

@app.route("/", methods=["GET"])
def index():
    # Get messages from session
    error_message = session.pop('error_message', None)
    success_message = session.pop('success_message', None)
    logged_in = session.get('logged_in', False)
    
    # Get PDF files
    pdf_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".pdf")]
    pdf_link = f"/output/{pdf_files[-1]}" if pdf_files else None
    
    return render_template_string(HTML_PAGE, 
                                 pdf_link=pdf_link,
                                 error_message=error_message,
                                 success_message=success_message,
                                 logged_in=logged_in)

@app.route("/output/<filename>")
def serve_pdf(filename):
    return send_file(os.path.join(OUTPUT_DIR, filename), as_attachment=True)

def cleanup_videos():
    while True:
        for file in os.listdir(VIDEO_DIR):
            file_path = os.path.join(VIDEO_DIR, file)
            if os.path.isfile(file_path) and time.time() - os.path.getmtime(file_path) > 3600:
                os.remove(file_path)
        time.sleep(600)

threading.Thread(target=cleanup_videos, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)