import requests
import subprocess

SERVER_URL = "http://your-server-ip:8080"

def request_video_download(video_url):
    response = requests.post(f"{SERVER_URL}/download", json={"url": video_url})
    print(response.json())

def download_video():
    response = requests.get(f"{SERVER_URL}/get_video", stream=True)
    if response.status_code == 200:
        with open("video.mp4", "wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                f.write(chunk)
        print("Видео загружено на локальный ПК")
    else:
        print("Ошибка скачивания видео")

def process_video():
    command = "python3 process_video.py video.mp4"
    subprocess.run(command, shell=True)

if __name__ == "__main__":
    video_url = input("Введите ссылку на YouTube: ")
    request_video_download(video_url)
    download_video()
    process_video()
