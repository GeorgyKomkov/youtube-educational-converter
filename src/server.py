from flask import Flask, request, jsonify, render_template_string, send_file
import subprocess
import os
import time
import threading

app = Flask(__name__)

VIDEO_DIR = "/app/videos"
os.makedirs(VIDEO_DIR, exist_ok=True)

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
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

# 🔹 Скачивание видео с ограничением на 1 процесс
@app.route("/download", methods=["POST"])
def download_video():
    global lock
    video_url = request.form.get("url") or request.json.get("url")
    if not video_url:
        return jsonify({"error": "URL обязателен"}), 400

    filename = os.path.join(VIDEO_DIR, "video.mp4")

    with lock:  # Блокируем процесс, пока скачивание не завершится
        command = f"yt-dlp -f best -o {filename} {video_url}"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            return jsonify({"error": f"Ошибка скачивания: {result.stderr}"}), 500

    if not os.path.exists(filename):
        return jsonify({"error": "Ошибка скачивания видео: файл не создан"}), 500

    return jsonify({"message": "Видео скачано", "file": filename})

# 🔹 API для скачивания видео на локальный ПК
@app.route("/get_video", methods=["GET"])
def get_video():
    filename = os.path.join(VIDEO_DIR, "video.mp4")
    if not os.path.exists(filename):
        return jsonify({"error": "Видео не найдено"}), 404
    return send_file(filename, as_attachment=True)

# 🔹 Фоновая очистка старых видео (каждые 10 минут удаляет файлы старше 1 часа)
def cleanup_videos():
    while True:
        for file in os.listdir(VIDEO_DIR):
            file_path = os.path.join(VIDEO_DIR, file)
            if os.path.isfile(file_path) and time.time() - os.path.getmtime(file_path) > 3600:
                os.remove(file_path)
        time.sleep(600)  # Проверять каждые 10 минут

# Запускаем очистку в фоновом потоке
threading.Thread(target=cleanup_videos, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
