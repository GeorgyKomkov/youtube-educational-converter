from flask import Flask, request, jsonify, render_template_string, send_file
import subprocess
import os

app = Flask(__name__)

VIDEO_DIR = "/app/videos"
os.makedirs(VIDEO_DIR, exist_ok=True)

# 📌 HTML-страница для пользователя
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

@app.route("/download", methods=["POST"])
def download_video():
    video_url = request.form.get("url") or request.json.get("url")
    if not video_url:
        return jsonify({"error": "URL обязателен"}), 400

    filename = os.path.join(VIDEO_DIR, "video.mp4")
    command = f"yt-dlp -o {filename} {video_url}"
    subprocess.run(command, shell=True)

    if not os.path.exists(filename):
        return jsonify({"error": "Ошибка скачивания видео"}), 500

    return jsonify({"message": "Видео скачано", "file": filename})

@app.route("/get_video", methods=["GET"])
def get_video():
    filename = os.path.join(VIDEO_DIR, "video.mp4")
    if not os.path.exists(filename):
        return jsonify({"error": "Видео не найдено"}), 404
    return send_file(filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
