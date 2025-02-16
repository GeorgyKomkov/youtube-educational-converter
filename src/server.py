from flask import Flask, request, jsonify, render_template_string
import subprocess
import os

app = Flask(__name__)

# HTML-страница для пользователей
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
    video_url = request.form.get("url")
    if not video_url:
        return jsonify({"error": "URL is required"}), 400

    filename = "video.mp4"
    command = f"yt-dlp -o {filename} {video_url}"
    subprocess.run(command, shell=True)

    return jsonify({"message": "Видео скачано", "file": filename})

@app.route("/get_result", methods=["GET"])
def get_result():
    if os.path.exists("result.txt"):
        with open("result.txt", "r") as f:
            return jsonify({"text": f.read()})
    return jsonify({"error": "Результат не найден"}), 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
