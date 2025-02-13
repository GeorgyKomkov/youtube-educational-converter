# YouTube Video to Educational Textbook Converter v.1.0.0

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker Support](https://img.shields.io/badge/Docker-✓-2496ED)](https://www.docker.com/)

Интеллектуальный конвертер обучающих видео YouTube в структурированные учебные материалы.  
Автоматическая транскрипция, захват ключевых кадров и семантическое связывание контента.

---

## 📌 Основные возможности

- ⬇️ **Скачивание видео** с YouTube (включая поддержку прокси).
- 🔊 **Транскрибация аудио** через OpenAI Whisper (локальные модели).
- 🖼️ **Автоматический захват кадров** с описанием через BLIP.
- 🔍 **Семантическое сопоставление** текста и изображений.
- 📁 **Гибкая конфигурация** через YAML-файл.
- 🐳 **Docker-поддержка** для быстрого развёртывания.
- 📤 **Экспорт результатов** в Markdown.

---

## 🚀 Установка

### Предварительные требования

1. **FFmpeg** (обязательно):
 # Ubuntu/Debian
   ```bash
   sudo apt-get install ffmpeg
   ```
   # Windows (через Chocolatey)
   ```bash
   choco install ffmpeg
   ```
   # MacOS
   ```bash
   brew install ffmpeg
   ```

## Клонируйте репозиторий:
 ```bash
   git clone https://github.com/GeorgyKomkov/youtube-educational-converter.git
   cd your-repo
   ```
 ## Установите зависимости:
 ```bash
   pip install -r requirements.txt
   ```
## Запуск через Docker
 ```bash
   docker-compose build
   docker-compose up
   ```




