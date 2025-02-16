import requests
import subprocess

SERVER_URL = "http://your-server-ip:8080"

def download_video():
    response = requests.post(f"{SERVER_URL}/download", json={"url": "YOUTUBE_VIDEO_URL"})
    print(response.json())

def process_video():
    command = "python3 process_video.py video.mp4"
    subprocess.run(command, shell=True)

def send_result():
    with open("result.txt", "r") as f:
        data = {"text": f.read()}
    response = requests.post(f"{SERVER_URL}/upload_result", json=data)
    print(response.json())

if __name__ == "__main__":
    download_video()
    process_video()
    send_result()
