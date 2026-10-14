Руководство разработчика
========================

Настройка окружения
-------------------

1. Клонируйте репозиторий: ``git clone https://github.com/sskkrays/Fs_booking.git``
2. Создайте venv: ``python -m venv .venv``
3. Активируйте: ``.venv\\Scripts\\Activate.ps1`` (Windows) или ``source .venv/bin/activate`` (Linux).
4. Установите зависимости: ``pip install -r requirements.txt``.

Структура проекта
-----------------

Весь код в файле ``fs_booking.py``. Внутри разделён на секции:

- DOMAIN LAYER — бизнес-логика
- DATA LAYER — ORM-модели и репозитории
- UI LAYER — интерфейс на PyQt5
- ENTRY POINT — точка входа

Сборка в exe
------------

``pyinstaller --onefile --windowed --name FS_Booking fs_booking.py``