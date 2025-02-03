# YouTube Video to Educational Textbook Converter

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Интеллектуальный конвертер обучающих видео YouTube в структурированные учебные материалы с автоматической транскрипцией, ключевыми кадрами и семантическим связыванием контента.

## 📌 Основные возможности

- ⬇️ Скачивание видео с YouTube в максимальном качестве
- 🔊 Транскрибация аудио с помощью OpenAI Whisper
- 🖼️ Автоматический захват ключевых кадров
- 🤖 Генерация описаний изображений с использованием BLIP
- 🔍 Семантическое сопоставление текста и визуального контента
- 📚 Экспорт в форматы Markdown и PDF
- ⚡ Оптимизация для GPU (поддержка CUDA)

## 📥 Установка

### Предварительные требования

1. **FFmpeg** (обязательно):
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows (используя chocolatey)
choco install ffmpeg

# MacOS
brew install ffmpeg
# Ubuntu/Debian
sudo apt-get install wkhtmltopdf

# Windows: https://wkhtmltopdf.org/downloads.html
```
## Установка Python-зависимостей
```bash
git clone https://github.com/yourusername/youtube-educational-converter.git
cd youtube-educational-converter
pip install -r requirements.txt
```
## Базовый запуск:
```bash
python src/main.py --url "https://youtu.be/your-video-id"
```
## Расширенные параметры:
```bash
python src/main.py \
  --url "https://youtu.be/your-video-id" \
  --output-format pdf \
  --frame-mode scenes \
  --max-frames 50 \
  --model large \
  --quality high
  ```