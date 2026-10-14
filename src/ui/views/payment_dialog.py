"""Диалог внесения оплаты за бронь."""

from decimal import Decimal

from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
)

from src.data.database import get_session
from src.data.orm_models import BookingORM


class PaymentDialog(QDialog):
    """Диалог оплаты — предоплата или полная."""

    def __init__(self, main, booking_id: int):
        super().__init__()
        self.main = main
        self.booking_id = booking_id
        self.setWindowTitle(f"Оплата брони #{booking_id}")
        self.setMinimumWidth(420)
        self._build()

    def _build(self):
        with get_session() as s:
            booking = s.get(BookingORM, self.booking_id)
            if not booking:
                self.total = Decimal("0")
                self.prepayment = Decimal("0")
            else:
                self.total = Decimal(booking.total_price or 0)
                self.prepayment = Decimal(getattr(booking, "prepayment", 0) or 0)

        form = QFormLayout(self)

        # Информация о брони
        info = QLabel(
            f"Итоговая сумма: {self.total:.2f} ₽\n"
            f"Внесено: {self.prepayment:.2f} ₽\n"
            f"Остаток: {self.total - self.prepayment:.2f} ₽"
        )
        info.setStyleSheet(
            "font-size: 11pt; padding: 10px; "
            "background-color: #FDF6E3; border-radius: 6px;"
        )
        form.addRow(info)

        # Выбор суммы
        self.amount_combo = QComboBox()

        prepayment_amount = (self.total * Decimal("0.15")).quantize(Decimal("0.01"))
        remaining = self.total - self.prepayment

        if self.prepayment == 0:
            self.amount_combo.addItem(
                f"Предоплата 15% — {prepayment_amount:.2f} ₽",
                ("prepayment", prepayment_amount),
            )

        if remaining > 0:
            self.amount_combo.addItem(
                f"Полная оплата — {remaining:.2f} ₽",
                ("full", remaining),
            )

        form.addRow("Сумма оплаты:", self.amount_combo)

        # Способ оплаты
        self.method_combo = QComboBox()
        self.method_combo.addItem("Карта", "card")
        self.method_combo.addItem("Наличные", "cash")
        self.method_combo.addItem("СБП", "sbp")
        form.addRow("Способ:", self.method_combo)

        # Комментарий
        self.comment_input = QLineEdit()
        self.comment_input.setPlaceholderText("Комментарий (необязательно)")
        form.addRow("Комментарий:", self.comment_input)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._on_pay)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def _on_pay(self):
        """Сохраняет оплату и обновляет статус."""
        data = self.amount_combo.currentData()
        if not data:
            self.main.show_error("Нет доступных сумм для оплаты.")
            return

        kind, amount = data

        # Обновляем в БД
        with get_session() as s:
            booking = s.get(BookingORM, self.booking_id)
            if not booking:
                self.main.show_error("Бронь не найдена.")
                return

            old_prepay = Decimal(getattr(booking, "prepayment", 0) or 0)
            new_prepay = old_prepay + amount
            booking.prepayment = new_prepay

            # Обновление статуса
            from src.data.orm_models import StatusORM
            from sqlalchemy import select

            if kind == "prepayment":
                status = s.scalar(
                    select(StatusORM).where(StatusORM.name == "Подтверждена")
                )
                if status:
                    booking.status_id = status.status_id
            elif kind == "full":
                status = s.scalar(
                    select(StatusORM).where(StatusORM.name == "Завершена")
                )
                if status:
                    booking.status_id = status.status_id

            s.commit()

        if kind == "prepayment":
            self.main.show_info(
                f"Предоплата {amount:.2f} ₽ внесена. "
                f"Бронь подтверждена."
            )
        else:
            self.main.show_info(
                f"Оплата {amount:.2f} ₽ внесена. "
                f"Бронь завершена."
            )

        self.accept()