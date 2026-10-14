"""Список броней (Figma: 'Брони')."""

from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui.widgets.common import build_topbar, make_button, make_table
from src.ui.views.booking_dialog import BookingDialog
from src.ui.views.payment_dialog import PaymentDialog
from src.data.database import get_session
from src.data.orm_models import StatusORM
from sqlalchemy import select


class BookingView(QWidget):
    """Список броней с созданием, сменой статуса и удалением."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(10)

        root.addLayout(build_topbar(self.main, "Брони"))

        # ---------- Кнопки действий ----------
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addWidget(make_button("+ Создать", self._on_create, accent=True))

        user = self.main.current_user
        is_admin = bool(user and user.role_id == 1)
        if is_admin:
            actions.addWidget(make_button("Сменить статус", self._on_change_status))

        actions.addWidget(make_button("Обновить", self.refresh))
        actions.addWidget(make_button("Оплатить", self._on_pay, accent=True))
        actions.addWidget(make_button("Удалить выбранную",
                                      self._on_delete, danger=True))

        actions.addStretch()
        root.addLayout(actions)

        # --- Строка поиска по ID ---
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        search_label = QLabel("Поиск по ID:")
        search_label.setFixedWidth(90)
        search_row.addWidget(search_label)

        self.search_id = QLineEdit()
        self.search_id.setPlaceholderText("Введите ID брони...")
        self.search_id.setFixedWidth(200)
        self.search_id.returnPressed.connect(self.refresh)
        search_row.addWidget(self.search_id)

        search_row.addWidget(make_button("Найти", self.refresh, accent=True))
        search_row.addWidget(make_button("Сбросить", self._reset_search))
        search_row.addStretch()
        root.addLayout(search_row)

        self.table = make_table(
            ["ID", "Клиент", "Зал", "Начало", "Окончание", "Статус", "Сумма"]
        )
        root.addWidget(self.table, stretch=1)

    def refresh(self):
        """Обновляет список броней. Учитывает фильтр по ID."""
        user = self.main.current_user
        is_admin = bool(user and user.role and "админ" in user.role.name.lower())

        if is_admin:
            bookings = self.main.booking_repo.list_all()
        else:
            bookings = self.main.booking_repo.list_by_user(user.user_id)

        # --- Фильтр по ID ---
        search_text = self.search_id.text().strip()
        if search_text:
            try:
                search_id = int(search_text)
                bookings = [b for b in bookings if b.booking_id == search_id]
            except ValueError:
                bookings = []

        self.table.setRowCount(len(bookings))
        for i, b in enumerate(bookings):
            values = [
                str(b.booking_id),
                b.client.name if b.client else "—",
                b.hall.name if b.hall else "—",
                b.start_datetime.strftime("%d.%m.%Y %H:%M"),
                b.end_datetime.strftime("%d.%m.%Y %H:%M"),
                b.status.name if b.status else "—",
                f"{b.total_price} ₽",
            ]
            for j, v in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(v))

    def _reset_search(self):
        """Очищает поле поиска и обновляет таблицу."""
        self.search_id.clear()
        self.refresh()


    def _on_create(self):
        dlg = BookingDialog(self.main)
        if dlg.exec_() == dlg.Accepted:
            self.refresh()

    def _on_change_status(self):
        """Диалог с кнопками смены статуса выбранной брони."""
        row = self.table.currentRow()
        if row < 0:
            self.main.show_error("Выберите бронь.")
            return

        booking_id = int(self.table.item(row, 0).text())

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Смена статуса брони #{booking_id}")
        dlg.setMinimumWidth(360)
        vbox = QVBoxLayout(dlg)

        label = QLabel("Выберите новое состояние брони:")
        label.setStyleSheet("font-size:11pt; margin-bottom:8px;")
        vbox.addWidget(label)

        actions = [
            ("Подтвердить (внесена предоплата 15%)", self._set_confirmed),
            ("Завершить (клиент пришёл, оплатил остаток)", self._set_completed),
            ("Не явился (предоплата внесена, но не пришёл)", self._set_no_show),
            ("Отменить бронь", self._set_cancelled),
        ]

        for text, handler in actions:
            btn = QPushButton(text)
            btn.setFixedHeight(40)
            btn.setStyleSheet(
                "QPushButton {"
                "  background-color: #6F8E9E;"
                "  color: white;"
                "  border: none;"
                "  border-radius: 6px;"
                "  font-size: 10pt;"
                "  text-align: left;"
                "  padding: 0 12px;"
                "}"
                "QPushButton:hover { background-color: #5E7C8C; }"
            )
            btn.clicked.connect(
                lambda checked=False, b_id=booking_id, h=handler:
                (h(b_id) and (self.refresh(), dlg.accept()))
            )
            vbox.addWidget(btn)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setFixedHeight(32)
        cancel_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #C8D4DA;"
            "  color: #2B2B2B;"
            "  border: none;"
            "  border-radius: 6px;"
            "}"
            "QPushButton:hover { background-color: #B7C9D3; }"
        )
        cancel_btn.clicked.connect(dlg.reject)
        vbox.addWidget(cancel_btn)

        dlg.exec_()

    def _set_confirmed(self, booking_id):
        if self.main.booking_repo.confirm_prepayment(booking_id):
            self.main.show_info("Бронь подтверждена (предоплата 15%).")
            return True
        self.main.show_error("Не удалось подтвердить бронь.")
        return False

    def _set_completed(self, booking_id):
        if self.main.booking_repo.complete_booking(booking_id):
            self.main.show_info("Бронь завершена.")
            return True
        return False

    def _set_no_show(self, booking_id):
        if self.main.booking_repo.mark_no_show(booking_id):
            self.main.show_info("Бронь помечена как «Не явился».")
            return True
        return False

    def _set_cancelled(self, booking_id):
        if self.main.booking_repo.cancel_booking(booking_id):
            self.main.show_info("Бронь отменена.")
            return True
        return False

    def _set_confirmed(self, booking_id):
        if self.main.booking_repo.confirm_prepayment(booking_id):
            self.main.show_info("Бронь подтверждена (предоплата 15%).")
            return True
        self.main.show_error("Не удалось подтвердить бронь.")
        return False

    def _set_completed(self, booking_id):
        if self.main.booking_repo.complete_booking(booking_id):
            self.main.show_info("Бронь завершена.")
            return True
        return False

    def _set_no_show(self, booking_id):
        if self.main.booking_repo.mark_no_show(booking_id):
            self.main.show_info("Бронь помечена как «Не явился».")
            return True
        return False

    def _set_cancelled(self, booking_id):
        if self.main.booking_repo.cancel_booking(booking_id):
            self.main.show_info("Бронь отменена.")
            return True
        return False



        btn.clicked.connect(
                lambda checked=False, b_id=booking_id, h=handler:
                (h(b_id) and (self.refresh(), dlg.accept()))
            )
        vbox.addWidget(btn)

        cancel_btn = QPushButton("Отмена")
        cancel_btn.setFixedHeight(32)
        cancel_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #C8D4DA;"
            "  color: #2B2B2B;"
            "  border: none;"
            "  border-radius: 6px;"
            "}"
            "QPushButton:hover { background-color: #B7C9D3; }"
        )
        cancel_btn.clicked.connect(dlg.reject)
        vbox.addWidget(cancel_btn)

        dlg.exec_()

    def _set_confirmed(self, booking_id):
        if self.main.booking_repo.confirm_prepayment(booking_id):
            self.main.show_info("Бронь подтверждена (предоплата 15%).")
            return True
        self.main.show_error("Не удалось подтвердить бронь.")
        return False

    def _set_completed(self, booking_id):
        if self.main.booking_repo.complete_booking(booking_id):
            self.main.show_info("Бронь завершена.")
            return True
        return False

    def _set_no_show(self, booking_id):
        if self.main.booking_repo.mark_no_show(booking_id):
            self.main.show_info("Бронь помечена как «Не явился».")
            return True
        return False

    def _set_cancelled(self, booking_id):
        if self.main.booking_repo.cancel_booking(booking_id):
            self.main.show_info("Бронь отменена.")
            return True
        return False

    def _on_pay(self):
        """Открывает диалог оплаты выбранной брони."""
        row = self.table.currentRow()
        if row < 0:
            self.main.show_error("Выберите бронь.")
            return
        booking_id = int(self.table.item(row, 0).text())

        dlg = PaymentDialog(self.main, booking_id)
        if dlg.exec_() == dlg.Accepted:
            self.refresh()

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            self.main.show_error("Выберите бронь.")
            return
        booking_id = int(self.table.item(row, 0).text())
        if self.main.booking_repo.delete(booking_id):
            self.main.show_info("Бронь удалена.")
            self.refresh()

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)