"""Точка входа приложения FS.Booking."""

import sys
from PyQt5.QtWidgets import QApplication

from src.data.database import init_db
from src.data.seed import seed_database
from src.ui.main_window import MainWindow
from src.ui.style import APP_STYLE


def main():
    """Инициализирует БД и запускает приложение."""
    init_db()
    seed_database()

    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()