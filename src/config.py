"""
Конфигурация приложения FS.Booking.

Содержит пути к файлам и базовые настройки.
"""

import sys
from pathlib import Path


def get_base_dir() -> Path:
    """
    Возвращает базовую папку проекта.

    Логика:
    - Если приложение запущено из exe (PyInstaller) — папка рядом с exe.
    - Если из исходников — папка на уровень выше src.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
DATABASE_PATH = BASE_DIR / "fs_booking.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"