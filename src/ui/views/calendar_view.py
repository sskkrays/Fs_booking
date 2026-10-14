"""Календарь броней (Figma: 'Дашборд/Календарь')."""

from PyQt5.QtCore import QDateTime, Qt
from PyQt5.QtWidgets import (
    QButtonGroup,
    QDateTimeEdit,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui.widgets.common import build_topbar, make_button, make_table


class CalendarView(QWidget):
    """Календарь броней: выбор одного дня или периода."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.mode = "day"  # day — один день, range — период
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        root.addLayout(build_topbar(self.main, "Календарь броней"))

        # ---------- Переключатель режима ----------
        mode_row = QHBoxLayout()
        mode_row.setSpacing(14)
        mode_row.addWidget(QLabel("Режим:"))

        self.radio_day = QRadioButton("Один день")
        self.radio_range = QRadioButton("Период")
        self.radio_day.setChecked(True)

        self.radio_day.toggled.connect(self._on_mode_changed)
        self.radio_range.toggled.connect(self._on_mode_changed)

        mode_row.addWidget(self.radio_day)
        mode_row.addWidget(self.radio_range)
        mode_row.addStretch()
        root.addLayout(mode_row)

        # ---------- Поля выбора даты ----------
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)
        filter_row.setAlignment(Qt.AlignLeft)

        # Поле «Дата» — для режима «Один день»
        self.label_date = QLabel("Дата:")
        self.label_date.setFixedWidth(50)
        filter_row.addWidget(self.label_date)

        self.date_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setFixedWidth(170)
        self.date_edit.setCalendarPopup(True)
        filter_row.addWidget(self.date_edit)

        # Поля «С» и «По» — для режима «Период»
        self.label_from = QLabel("С:")
        self.label_from.setFixedWidth(50)
        filter_row.addWidget(self.label_from)

        self.date_from = QDateTimeEdit(QDateTime.currentDateTime())
        self.date_from.setDisplayFormat("dd.MM.yyyy")
        self.date_from.setFixedWidth(170)
        self.date_from.setCalendarPopup(True)
        filter_row.addWidget(self.date_from)

        self.label_to = QLabel("По:")
        self.label_to.setFixedWidth(50)
        filter_row.addWidget(self.label_to)

        self.date_to = QDateTimeEdit(QDateTime.currentDateTime())
        self.date_to.setDisplayFormat("dd.MM.yyyy")
        self.date_to.setFixedWidth(170)
        self.date_to.setCalendarPopup(True)
        filter_row.addWidget(self.date_to)

        filter_row.addWidget(make_button("Показать", self.refresh, accent=True))
        filter_row.addStretch()
        root.addLayout(filter_row)

        # ---------- Таблица ----------
        self.table = make_table(
            ["Зал", "Начало", "Окончание", "Клиент", "Статус"]
        )
        root.addWidget(self.table, stretch=1)

        # Применяем начальный режим — «Один день»
        self._apply_mode()

    def _on_mode_changed(self):
        """Переключает режим и обновляет видимость полей."""
        self.mode = "day" if self.radio_day.isChecked() else "range"
        self._apply_mode()
        self.refresh()

    def _apply_mode(self):
        """Показывает/скрывает поля в зависимости от режима."""
        if self.mode == "day":
            # Режим «Один день»
            self.label_date.setVisible(True)
            self.date_edit.setVisible(True)

            self.label_from.setVisible(False)
            self.date_from.setVisible(False)
            self.label_to.setVisible(False)
            self.date_to.setVisible(False)
        else:
            # Режим «Период»
            self.label_date.setVisible(False)
            self.date_edit.setVisible(False)

            self.label_from.setVisible(True)
            self.date_from.setVisible(True)
            self.label_to.setVisible(True)
            self.date_to.setVisible(True)

    def refresh(self):
        """Показывает брони за выбранный день или период."""
        if self.mode == "day":
            # Один день
            day = self.date_edit.dateTime().toPyDateTime()
            start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            # Период
            start = self.date_from.dateTime().toPyDateTime()
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)

            end = self.date_to.dateTime().toPyDateTime()
            end = end.replace(hour=23, minute=59, second=59, microsecond=999999)

            if end < start:
                self.main.show_error("Дата 'По' должна быть позже даты 'С'.")
                return

        # Запрос к БД — через репозиторий
        with get_session() as s:
            from sqlalchemy.orm import joinedload
            from sqlalchemy import select
            from src.data.orm_models import BookingORM

            stmt = (
                select(BookingORM)
                .options(
                    joinedload(BookingORM.client),
                    joinedload(BookingORM.hall),
                    joinedload(BookingORM.status),
                )
                .where(
                    BookingORM.start_datetime >= start,
                    BookingORM.start_datetime <= end,
                )
                .order_by(BookingORM.start_datetime)
            )
            bookings = list(s.scalars(stmt).unique().all())

        self.table.setRowCount(len(bookings))
        for i, b in enumerate(bookings):
            values = [
                b.hall.name if b.hall else "—",
                b.start_datetime.strftime("%d.%m.%Y %H:%M"),
                b.end_datetime.strftime("%d.%m.%Y %H:%M"),
                b.client.name if b.client else "—",
                b.status.name if b.status else "—",
            ]
            for j, v in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(v))

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)


# Импорт в конце — чтобы не конфликтовал с классом
from src.data.database import get_session  # noqa: E402