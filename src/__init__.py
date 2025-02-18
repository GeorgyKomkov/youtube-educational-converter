# Отсутствует __init__.py, что может вызвать проблемы с импортами

import os
import sys
import logging
import yaml
from pathlib import Path

# Настройка логирования
def setup_logging():
    """Настройка системы логирования"""
    try:
        config_path = Path(__file__).parent.parent / 'config' / 'logging.yaml'
        if config_path.exists():
            with open(config_path, 'r') as f:
                try:
                    config = yaml.safe_load(f)
                    logging.config.dictConfig(config)
                except Exception as e:
                    print(f"Error parsing logging config: {e}")
                    raise
        else:
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
    except Exception as e:
        print(f"Error setting up logging: {e}")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

# Инициализация путей
ROOT_DIR = Path(__file__).parent.parent
TEMP_DIR = ROOT_DIR / 'temp'
OUTPUT_DIR = ROOT_DIR / 'output'
VIDEO_DIR = ROOT_DIR / 'videos'
CACHE_DIR = ROOT_DIR / 'cache'
LOG_DIR = ROOT_DIR / 'logs'

# Создание необходимых директорий
for directory in [TEMP_DIR, OUTPUT_DIR, VIDEO_DIR, CACHE_DIR, LOG_DIR]:
    directory.mkdir(exist_ok=True)

# Добавляем корневую директорию в PYTHONPATH
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

# Загрузка конфигурации
def load_config():
    """Загрузка и валидация конфигурации"""
    try:
        config_path = ROOT_DIR / 'config' / 'config.yaml'
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
            
        with open(config_path, 'r') as f:
            try:
                config = yaml.safe_load(f)
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in config: {e}")
            
        # Проверка обязательных параметров
        required = ['temp_dir', 'output_dir', 'video_dir']
        missing = [param for param in required if param not in config]
        if missing:
            raise ValueError(f"Missing required parameters: {', '.join(missing)}")
            
        return config
        
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        raise

# Инициализация
setup_logging()
logger = logging.getLogger(__name__)

try:
    config = load_config()
except Exception as e:
    logger.error(f"Failed to initialize application: {e}")
    sys.exit(1)

__version__ = '1.0.0'

os.makedirs('/app/logs', exist_ok=True)
