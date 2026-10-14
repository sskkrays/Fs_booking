"""Единый стиль приложения FS.Booking."""

APP_STYLE = """
QWidget { background-color:#EAF2F5; color:#2B2B2B;
          font-family:'Segoe UI'; font-size:10pt; }
QMainWindow { background-color:#EAF2F5; }
QPushButton { background-color:#6F8E9E; color:white; border:none;
              padding:8px 16px; border-radius:6px; }
QPushButton:hover { background-color:#5E7C8C; }
QPushButton#accent { background-color:#D4A373; }
QPushButton#accent:hover { background-color:#C09066; }
QPushButton#danger { background-color:#C97B7B; }
QLineEdit, QComboBox, QDateTimeEdit, QTextEdit {
    background-color:#FDF6E3; border:1px solid #C8D4DA;
    border-radius:6px; padding:6px;
}
QTableWidget { background-color:#FDF6E3; gridline-color:#C8D4DA;
               border:1px solid #C8D4DA; border-radius:6px; }
QHeaderView::section { background-color:#D9E4EA; padding:6px; border:none; }
QLabel#title { font-size:14pt; font-weight:bold; }
QLabel#subtitle { font-size:11pt; font-weight:bold; }
QFrame#card { background-color:#B7C9D3; border-radius:10px; }
QFrame#tile { background-color:#FDF6E3; border:1px solid #C8D4DA;
              border-radius:8px; }
"""