"""Экран регистрации (Figma: 'Регистрация')."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QLabel, QLineEdit, QVBoxLayout, QWidget
from sqlalchemy import select

from src.data.database import get_session
from src.data.orm_models import RoleORM
from src.domain.exceptions import ValidationError
from src.domain.services import hash_password
from src.ui.widgets.common import make_button


class RegisterView(QWidget):
    """Форма регистрации нового пользователя (роль 'Клиент')."""

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
        card.setFixedWidth(340)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 24, 24, 24)
        cl.setSpacing(10)

        title = QLabel("Регистрация")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("subtitle")

        self.full_name = QLineEdit()
        self.full_name.setPlaceholderText("ФИО")

        self.login = QLineEdit()
        self.login.setPlaceholderText("Логин")

        self.password = QLineEdit()
        self.password.setPlaceholderText("Пароль")
        self.password.setEchoMode(QLineEdit.Password)

        self.password2 = QLineEdit()
        self.password2.setPlaceholderText("Повтор пароля")
        self.password2.setEchoMode(QLineEdit.Password)

        btn_submit = make_button("Зарегистрироваться", self._on_submit, accent=True)
        btn_back = make_button("Назад", self.main.show_login)

        for w in (title, self.full_name, self.login, self.password,
                  self.password2, btn_submit, btn_back):
            cl.addWidget(w)

        root.addWidget(header)
        root.addSpacing(16)
        root.addWidget(card, alignment=Qt.AlignCenter)

    def _on_submit(self):
        if not all([self.full_name.text().strip(),
                    self.login.text().strip(),
                    self.password.text(),
                    self.password2.text()]):
            self.main.show_error("Заполните все поля.")
            return

        if self.password.text() != self.password2.text():
            self.main.show_error("Пароли не совпадают.")
            return

        if self.main.user_repo.get_by_login(self.login.text().strip()):
            self.main.show_error("Логин уже занят.")
            return

        try:
            pwd_hash = hash_password(self.password.text())
        except ValidationError as e:
            self.main.show_error(str(e))
            return

        with get_session() as s:
            role = s.scalar(select(RoleORM).where(RoleORM.name == "Клиент"))
            role_id = role.role_id if role else 1

        self.main.user_repo.create(
            role_id,
            self.login.text().strip(),
            pwd_hash,
            self.full_name.text().strip(),
        )
        self.main.show_info("Регистрация успешна. Войдите в систему.")
        self.main.show_login()