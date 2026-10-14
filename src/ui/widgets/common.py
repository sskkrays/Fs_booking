"""Переиспользуемые компоненты интерфейса."""

from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)


def make_button(text, slot, accent=False, danger=False) -> QPushButton:
    """Создаёт стилизованную кнопку."""
    b = QPushButton(text)
    if accent:
        b.setObjectName("accent")
    elif danger:
        b.setObjectName("danger")
    b.clicked.connect(slot)
    return b


def make_table(headers) -> QTableWidget:
    """Создаёт QTableWidget с заголовками, прокруткой и без номеров строк."""
    t = QTableWidget()
    t.setColumnCount(len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    # Вертикальный скроллбар — всегда виден, если есть данные
    t.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    t.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    # Прокрутка по пикселям (плавнее)
    t.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
    t.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)

    t.setSelectionBehavior(QTableWidget.SelectRows)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(34)
    t.setStyleSheet(
        "QTableWidget { font-size: 11pt; }"
        "QHeaderView::section { font-size: 11pt; font-weight: bold; padding: 8px; }"
        "QScrollBar:vertical { width: 10px; background: #EAF2F5; }"
        "QScrollBar::handle:vertical { background: #B7C9D3; border-radius: 5px; }"
        "QScrollBar::handle:vertical:hover { background: #A5B8C2; }"
    )
    return t


def build_sidebar(main, items) -> QFrame:
    """Строит боковую панель с кнопками навигации."""
    side = QFrame()
    side.setFixedWidth(180)
    side.setStyleSheet("background-color:#FDF6E3; border-right:1px solid #C8D4DA;")
    layout = QVBoxLayout(side)
    layout.setContentsMargins(14, 18, 14, 18)
    layout.setSpacing(4)

    logo = QLabel("FS.Booking")
    logo.setObjectName("subtitle")
    logo.setStyleSheet("font-size:14pt; font-weight:bold; padding: 6px 4px;")
    layout.addWidget(logo)
    layout.addSpacing(20)

    sidebar_button_style = """
        QPushButton {
            background-color: #D9E4EA;
            color: #2B2B2B;
            text-align: left;
            padding: 12px 16px;
            border: 1px solid #C8D4DA;
            border-radius: 8px;
            font-size: 11pt;
        }
        QPushButton:hover {
            background-color: #B7C9D3;
            color: #1A1A1A;
        }
    """

    for text, slot in items:
        btn = make_button(text, slot)
        btn.setMinimumHeight(44)
        btn.setStyleSheet(sidebar_button_style)
        layout.addWidget(btn)
        layout.addSpacing(4)

    layout.addStretch()
    logout_btn = make_button("Выйти", main.logout, danger=True)
    logout_btn.setStyleSheet(sidebar_button_style)
    layout.addWidget(logout_btn)
    return side


def build_header(text: str) -> QLabel:
    """Строит заголовок экрана."""
    lbl = QLabel(text)
    lbl.setObjectName("title")
    return lbl


def build_topbar(main, title: str) -> QHBoxLayout:
    """Строит верхнюю панель с кнопкой 'Назад' и заголовком."""
    bar = QHBoxLayout()
    back_btn = QPushButton("← Назад в меню")
    back_btn.setObjectName("accent")
    back_btn.setFixedWidth(160)
    back_btn.clicked.connect(main.show_dashboard)
    bar.addWidget(back_btn)
    bar.addSpacing(10)
    bar.addWidget(build_header(title))
    bar.addStretch()
    return bar