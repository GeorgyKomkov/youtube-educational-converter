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
                config = yaml.safe_load(f)
            logging.config.dictConfig(config)
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

# Добавляем корневую директорию в PYTHONPATH
root_dir = Path(__file__).parent.parent
if str(root_dir) not in sys.path:
    sys.path.append(str(root_dir))

# Загрузка конфигурации
def load_config():
    """Загрузка и валидация конфигурации"""
    try:
        config_path = root_dir / 'config' / 'config.yaml'
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
            
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
        # Проверка обязательных параметров
        required = ['temp_dir', 'output_dir', 'video_dir']
        missing = [param for param in required if param not in config]
        if missing:
            raise ValueError(f"Missing required parameters: {', '.join(missing)}")
            
        # Создание необходимых директорий
        for dir_path in [config['temp_dir'], config['output_dir'], config['video_dir']]:
            os.makedirs(dir_path, exist_ok=True)
            
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
