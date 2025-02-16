# Отсутствует __init__.py, что может вызвать проблемы с импортами

import os
import sys

# Добавляем корневую директорию в PYTHONPATH
root_dir = os.path.dirname(os.path.dirname(__file__))
if root_dir not in sys.path:
    sys.path.append(root_dir)
