import sys
import traceback
from PyQt5.QtWidgets import QApplication

# Импорты оборачиваем в try, чтобы поймать ошибку импорта
try:
    from src.ui.main_window import MainWindow
    from src.ui.style import APP_STYLE
    from src.data.database import init_db
    # seed_database пока НЕ импортируем и НЕ вызываем
except Exception as e:
    print("--- КРИТИЧЕСКАЯ ОШИБКА ПРИ ИМПОРТЕ МОДУЛЕЙ ---")
    traceback.print_exc()
    sys.exit(1)

def main():
    try:
        print("--- Инициализация БД ---")
        init_db()
        print("--- БД инициализирована ---")
        
        print("--- Запуск GUI ---")
        app = QApplication(sys.argv)
        app.setStyleSheet(APP_STYLE)
        window = MainWindow()
        window.show()
        sys.exit(app.exec_())
        
    except Exception as e:
        print("--- ОШИБКА ПРИ ЗАПУСКЕ ПРИЛОЖЕНИЯ ---")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
