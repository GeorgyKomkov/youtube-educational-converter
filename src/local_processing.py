import requests
import subprocess
import os
import time
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SERVER_URL = "http://your-server-ip:8080"
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

def request_with_retry(func):
    def wrapper(*args, **kwargs):
        retries = 3
        for attempt in range(retries):
            try:
                return func(*args, **kwargs)
            except requests.exceptions.RequestException as e:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)
        return None
    return wrapper

def request_video_download(video_url):
    """Отправить запрос на скачивание видео на сервер"""
    try:
        response = requests.post(f"{SERVER_URL}/download", 
                                json={"url": video_url},
                                timeout=30)
        if response.status_code == 200:
            logger.info("Запрос на скачивание успешно отправлен")
            return response.json()
        else:
            logger.error(f"Ошибка при запросе: {response.status_code}, {response.text}")
            return None
    except requests.exceptions.ConnectionError:
        logger.error("Ошибка подключения к серверу")
        return None
    except requests.exceptions.Timeout:
        logger.error("Таймаут запроса")
        return None

def download_video():
    """Скачать видео с сервера на локальный ПК с повторными попытками"""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(f"{SERVER_URL}/get_video", stream=True, timeout=300)
            if response.status_code == 200:
                with open("video.mp4", "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                if os.path.exists("video.mp4") and os.path.getsize("video.mp4") > 1024:
                    logger.info("Видео успешно загружено на локальный ПК")
                    return True
                else:
                    logger.warning("Файл скачан, но имеет подозрительно малый размер")
            else:
                logger.error(f"Ошибка скачивания видео: {response.status_code}, {response.text}")
            
            if attempt < MAX_RETRIES - 1:
                logger.info(f"Повторная попытка через {RETRY_DELAY} секунд...")
                time.sleep(RETRY_DELAY)
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка соединения при скачивании: {e}")
            if attempt < MAX_RETRIES - 1:
                logger.info(f"Повторная попытка через {RETRY_DELAY} секунд...")
                time.sleep(RETRY_DELAY)
    
    logger.error(f"Не удалось скачать видео после {MAX_RETRIES} попыток")
    return False

def process_video():
    """Обработать скачанное видео"""
    if not os.path.exists("video.mp4"):
        logger.error("Видеофайл отсутствует, обработка невозможна")
        return False
    
    try:
        logger.info("Начинаем обработку видео...")
        command = "python3 src/process_video.py video.mp4"
        result = subprocess.run(command, shell=True, check=True, 
                               capture_output=True, text=True)
        logger.info("Видео успешно обработано")
        return True
    except subprocess.SubprocessError as e:
        logger.error(f"Ошибка при обработке видео: {e}")
        if hasattr(e, 'stderr'):
            logger.error(f"Stderr: {e.stderr}")
        return False

def upload_pdf(pdf_path):
    """Отправка PDF-учебника на сервер"""
    try:
        with open(pdf_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(f"{SERVER_URL}/upload_pdf", files=files)
        
        if response.status_code == 200:
            logger.info(f"PDF успешно загружен на сервер: {pdf_path}")
            return True
        else:
            logger.error(f"Ошибка загрузки PDF: {response.status_code}, {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка соединения с сервером при загрузке PDF: {e}")
        return False

if __name__ == "__main__":
    video_url = input("Введите ссылку на YouTube: ")
    
    # Шаг 1: Запрос на скачивание
    download_info = request_video_download(video_url)
    if not download_info:
        logger.error("Не удалось отправить запрос на скачивание. Выход.")
        exit(1)
    
    # Шаг 2: Скачивание видео локально
    if not download_video():
        logger.error("Не удалось скачать видео. Выход.")
        exit(1)
    
    # Шаг 3: Обработка видео
    if not process_video():
        logger.error("Не удалось обработать видео. Выход.")
        exit(1)
    
    # Шаг 4: Отправка PDF на сервер
    pdf_path = "output/video.pdf"  # Путь к PDF после обработки
    if not upload_pdf(pdf_path):
        logger.error("Не удалось загрузить PDF на сервер.")
        exit(1)
    
    logger.info("Все операции выполнены успешно!")
