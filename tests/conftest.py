import sys
from pathlib import Path


# Добавляем корень проекта в sys.path, чтобы импорты `app.*` работали
# при запуске тестов из любой рабочей директории.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
