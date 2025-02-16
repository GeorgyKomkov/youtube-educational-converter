from flask import Flask, request, jsonify, render_template_string, send_file
import subprocess
import os
import time
import threading

app = Flask(__name__)

VIDEO_DIR = "/app/videos"
OUTPUT_DIR = "/app/output"
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 🔹 Блокировка для контроля одновременного скачивания
lock = threading.Lock()

# 🔹 HTML-страница для ввода ссылки
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>YouTube Video Downloader</title>
</head>
<body>
    <h2>Введите ссылку на YouTube</h2>
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

@app.route("/download", methods=["POST"])
def download_video():
    global lock
    video_url = request.form.get("url") or request.json.get("url")
    
    if not video_url:
        return jsonify({"error": "URL обязателен"}), 400

    app.logger.info(f"Получен URL для скачивания: {video_url}")  # Логируем URL

    filename = os.path.join(VIDEO_DIR, "video.mp4")

    with lock:
        command = f"yt-dlp -o {filename} {video_url}"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            app.logger.error(f"Ошибка yt-dlp: {result.stderr}")
            return jsonify({
                "error": f"Ошибка скачивания: {result.stderr[:200]}...",
                "full_error": result.stderr
            }), 500

    if not os.path.exists(filename):
        return jsonify({"error": "Ошибка скачивания видео: файл не создан"}), 500

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
    pdf_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".pdf")]
    pdf_link = f"/output/{pdf_files[-1]}" if pdf_files else None
    return render_template_string(HTML_PAGE, pdf_link=pdf_link)

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

