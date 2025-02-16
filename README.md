# YouTube-Converter

## 📌 Описание
Этот проект позволяет скачивать видео с YouTube (через VPN) на сервере и обрабатывать его локально.

## 📌 Архитектура
- **Сервер** (VPN) скачивает видео.
- **Локальный ПК** обрабатывает видео (Whisper, AI).
- **Сервер** хранит результат и отдает его пользователям.

## 📌 Развертывание

### 1️⃣ Запуск сервера (VPN)
```bash
git clone https://github.com/your-repo/youtube-converter.git
cd youtube-converter
docker-compose up -d
