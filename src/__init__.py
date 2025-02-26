# Отсутствует __init__.py, что может вызвать проблемы с импортами

import os
import sys
import logging
import yaml
from pathlib import Path

print("Starting initialization...")  # Отладочный вывод

# Настройка логирования
def setup_logging():
    """Настройка системы логирования"""
    try:
        config_path = Path(__file__).parent.parent / 'config' / 'logging.yaml'
        print(f"Loading logging config from: {config_path}")  # Отладочный вывод
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                try:
                    config = yaml.safe_load(f)
                    # Создаем директории для логов
                    log_files = [
                        handler.get('filename') 
                        for handler in config.get('handlers', {}).values() 
                        if 'filename' in handler
                    ]
                    for log_file in log_files:
                        os.makedirs(os.path.dirname(log_file), exist_ok=True)
                    
                    # Используем базовую конфигурацию вместо dictConfig
                    logging.basicConfig(
                        level=config.get('root', {}).get('level', 'INFO'),
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        handlers=[
                            logging.StreamHandler(),
                            logging.FileHandler('/app/logs/app.log')
                        ]
                    )
                    print("Logging configuration loaded successfully")  # Отладочный вывод
                except Exception as e:
                    print(f"Error parsing logging config: {e}")
                    raise
        else:
            print("Logging config not found, using basic configuration")  # Отладочный вывод
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
for directory in [TEMP_DIR, OUTPUT_DIR, VIDEO_DIR, CACHE_DIR, LOG_DIR, ROOT_DIR / 'config']:
    try:
        directory.mkdir(exist_ok=True, parents=True)
        os.chmod(directory, 0o755)  # Установка прав доступа
        print(f"Created directory with permissions: {directory}")
    except Exception as e:
        print(f"Error creating directory {directory}: {e}")

# Добавляем корневую директорию в PYTHONPATH
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))
    print(f"Added {ROOT_DIR} to PYTHONPATH")  # Отладочный вывод

# Загрузка конфигурации
def load_config():
    """Загрузка и валидация конфигурации"""
    try:
        config_path = ROOT_DIR / 'config' / 'config.yaml'
        print(f"Loading config from: {config_path}")  # Отладочный вывод
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
            
        with open(config_path, 'r') as f:
            try:
                config = yaml.safe_load(f)
                print("Configuration loaded successfully")  # Отладочный вывод
            except yaml.YAMLError as e:
                raise ValueError(f"Invalid YAML in config: {e}")
            
        # Проверка обязательных параметров
        required = ['temp_dir', 'output_dir', 'video_dir']
        missing = [param for param in required if param not in config]
        if missing:
            raise ValueError(f"Missing required parameters: {', '.join(missing)}")
            
        return config
        
    except Exception as e:
        print(f"Error loading config: {e}")  # Отладочный вывод
        raise

# Инициализация
setup_logging()
logger = logging.getLogger(__name__)
logger.info("Starting application initialization")

try:
    config = load_config()
    logger.info("Application initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize application: {e}")
    sys.exit(1)

__version__ = '1.0.0'

# Создаем директорию для логов в контейнере
os.makedirs('/app/logs', exist_ok=True)
print("Initialization complete")  # Отладочный вывод
