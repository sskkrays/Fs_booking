"""Экран восстановления пароля через номер телефона."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from src.data.database import get_session
from src.data.orm_models import UserORM
from src.domain.services import hash_password, normalize_phone
from src.domain.exceptions import ValidationError
from src.ui.widgets.common import make_button


def generate_code() -> str:
    """Генерирует 6-значный код."""
    import random
    return str(random.randint(100000, 999999))


class ForgotView(QWidget):
    """Восстановление пароля через номер телефона."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        header = QLabel("FS.Booking")
        header.setObjectName("title")
        header.setAlignment(Qt.AlignCenter)

        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(400)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 24, 24, 24)
        cl.setSpacing(12)

        title = QLabel("Восстановление пароля")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("subtitle")

        info = QLabel(
            "Введите номер телефона, привязанный к аккаунту. "
            "На него придёт код для сброса пароля."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#2B2B2B; font-size:9pt;")

        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("+79911148234 или 89911148234")

        btn_send = make_button("Отправить код", self._on_send, accent=True)
        btn_back = make_button("Назад", self.main.show_login)

        cl.addWidget(title)
        cl.addWidget(info)
        cl.addWidget(self.phone_input)
        cl.addWidget(btn_send)
        cl.addWidget(btn_back)

        root.addWidget(header)
        root.addSpacing(16)
        root.addWidget(card, alignment=Qt.AlignCenter)

    def _on_send(self):
        """Отправляет код на телефон и открывает диалог ввода кода."""
        raw_phone = self.phone_input.text().strip()
        if not raw_phone:
            self.main.show_error("Введите номер телефона.")
            return

        # Нормализуем номер
        try:
            phone = normalize_phone(raw_phone)
        except ValidationError as e:
            self.main.show_error(str(e))
            return

        # Ищем пользователя по телефону
        with get_session() as s:
            user = s.scalar(select(UserORM).where(UserORM.phone == phone))

        if not user:
            self.main.show_error(
                "Пользователь с таким номером телефона не найден.\n"
                "Обратитесь к администратору."
            )
            return

        # Генерируем код и сохраняем в БД
        code = generate_code()
        with get_session() as s:
            u = s.get(UserORM, user.user_id)
            u.reset_code = code
            s.commit()

        # --- ИМИТАЦИЯ SMS ---
        # В реальном приложении здесь отправка SMS через шлюз.
        # Пока показываем код в диалоге.
        self.main.show_info(
            f"[ИМИТАЦИЯ SMS]\n\n"
            f"Код для восстановления: {code}\n\n"
            f"В реальном приложении код придёт на номер {phone}."
        )

        # Открываем диалог ввода кода
        dlg = ResetPasswordDialog(self.main, user.user_id)
        dlg.exec_()

        self.phone_input.clear()
        self.main.show_login()


class ResetPasswordDialog(QDialog):
    """Диалог ввода кода и нового пароля."""

    def __init__(self, main, user_id):
        super().__init__()
        self.main = main
        self.user_id = user_id
        self.setWindowTitle("Ввод кода")
        self.setMinimumWidth(380)
        self._build()

    def _build(self):
        form = QFormLayout(self)

        info = QLabel("Введите код и новый пароль.")
        info.setWordWrap(True)
        info.setStyleSheet("color:#2B2B2B; font-size:9pt;")
        form.addRow(info)

        self.code_input = QLineEdit()
        self.code_input.setPlaceholderText("6-значный код")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Новый пароль")
        self.password_input.setEchoMode(QLineEdit.Password)

        self.password2_input = QLineEdit()
        self.password2_input.setPlaceholderText("Повторите пароль")
        self.password2_input.setEchoMode(QLineEdit.Password)

        form.addRow("Код:", self.code_input)
        form.addRow("Новый пароль:", self.password_input)
        form.addRow("Повторите:", self.password2_input)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._on_save)
        bb.rejected.connect(self.reject)
        form.addRow(bb)

    def _on_save(self):
        """Проверяет код и меняет пароль."""
        code = self.code_input.text().strip()
        pwd1 = self.password_input.text()
        pwd2 = self.password2_input.text()

        if not code or not pwd1 or not pwd2:
            self.main.show_error("Заполните все поля.")
            return

        if pwd1 != pwd2:
            self.main.show_error("Пароли не совпадают.")
            return

        if len(pwd1) < 4:
            self.main.show_error("Пароль слишком короткий (минимум 4 символа).")
            return

        with get_session() as s:
            user = s.get(UserORM, self.user_id)
            if not user or user.reset_code != code:
                self.main.show_error("Неверный код.")
                return
            user.password_hash = hash_password(pwd1)
            user.reset_code = None
            s.commit()

        self.main.show_info("Пароль изменён. Войдите с новым паролем.")
        self.accept()