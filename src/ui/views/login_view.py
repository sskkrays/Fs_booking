"""Экран авторизации (Figma: 'Авторизация')."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFrame, QLabel, QLineEdit, QVBoxLayout, QWidget

from src.domain.services import verify_password
from src.ui.widgets.common import make_button


class LoginView(QWidget):
    """Форма входа в систему."""

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
        cl.setSpacing(12)

        title = QLabel("Вход в аккаунт")
        title.setAlignment(Qt.AlignCenter)
        title.setObjectName("subtitle")

        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Логин")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.Password)

        btn_login = make_button("Войти", self._on_login, accent=True)
        btn_reg = make_button("Регистрация", self.main.show_register)
        btn_forgot = make_button("Забыли пароль?", self.main.show_forgot)

        cl.addWidget(title)
        cl.addWidget(self.login_input)
        cl.addWidget(self.password_input)
        cl.addWidget(btn_login)
        cl.addWidget(btn_reg)
        cl.addWidget(btn_forgot)

        root.addWidget(header)
        root.addSpacing(16)
        root.addWidget(card, alignment=Qt.AlignCenter)

        self.password_input.returnPressed.connect(self._on_login)

    def _on_login(self):
        login = self.login_input.text().strip()
        password = self.password_input.text()

        if not login or not password:
            self.main.show_error("Введите логин и пароль.")
            return

        user = self.main.user_repo.get_by_login(login)
        if not user or not verify_password(password, user.password_hash):
            self.main.show_error("Неверный логин или пароль.")
            return

        self.main.current_user = user
        self.main.show_dashboard()