"""Профиль клиента (Figma: 'Мой профиль (клиент)')."""

from PyQt5.QtCore import Qt

from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui.widgets.common import (
    build_header,
    build_sidebar,
    make_button,
    make_table,
)
from src.ui.views.booking_dialog import BookingDialog


class ClientProfileView(QWidget):
    """Профиль клиента."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = build_sidebar(self.main, [
            ("Профиль", lambda: self.main.show_view(self)),
            ("Календарь", lambda: self.main.show_view(self.main.calendar_view)),
            ("Мои брони", lambda: self.main.show_view(self.main.booking_view)),
        ])
        root.addWidget(sidebar)

        body = QVBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(12)

        body.addWidget(build_header("Мой профиль"))

        info_card = QFrame()
        info_card.setStyleSheet(
            "background-color:#FDF6E3; border:1px solid #C8D4DA; "
            "border-radius:8px; padding:12px;"
        )
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(16, 12, 16, 12)

        self.info_label = QLabel()
        self.info_label.setStyleSheet("color:#2B2B2B; font-size:11pt;")
        info_layout.addWidget(self.info_label)
        body.addWidget(info_card)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(8)

        btn_new = make_button("+ Создать бронь", self._on_create_booking, accent=True)
        buttons_row.addWidget(btn_new)

        btn_edit = make_button("Редактировать профиль", self._on_edit_profile)
        buttons_row.addWidget(btn_edit)

        buttons_row.addStretch()
        body.addLayout(buttons_row)

        body.addWidget(QLabel("Мои брони:"))

        self.table = make_table(
            ["ID", "Зал", "Начало", "Окончание", "Статус", "Сумма", "Фото"]
        )
        body.addWidget(self.table)

        body.addWidget(make_button("Обновить", self.refresh),
                       alignment=Qt.AlignLeft)

        container = QWidget()
        container.setLayout(body)
        root.addWidget(container, stretch=1)

    def refresh(self):
        user = self.main.current_user
        if not user:
            return

        self.info_label.setText(
            f"<b>ФИО:</b> {user.full_name}<br>"
            f"<b>Логин:</b> {user.login}<br>"
            f"<b>Роль:</b> {user.role.name if user.role else 'Клиент'}"
        )

        bookings = self.main.booking_repo.list_by_user(user.user_id)
        self.table.setRowCount(len(bookings))
        for i, b in enumerate(bookings):
            values = [
                str(b.booking_id),
                b.hall.name if b.hall else "—",
                b.start_datetime.strftime("%d.%m.%Y %H:%M"),
                b.end_datetime.strftime("%d.%m.%Y %H:%M"),
                b.status.name if b.status else "—",
                f"{b.total_price} ₽",
            ]
            for j, v in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(v))

            # Колонка «Фото» — ссылка или кнопка
            url = getattr(b, "photo_url", None)
            if url:
                link = QLabel(f'<a href="{url}">Открыть фото</a>')
                link.setOpenExternalLinks(True)
                link.setStyleSheet("padding: 4px;")
                self.table.setCellWidget(i, 6, link)
            else:
                self.table.setItem(i, 6, QTableWidgetItem("—"))

    def _on_edit_profile(self):
        """Диалог редактирования профиля клиента: ФИО, логин, пароль."""
        from src.domain.services import hash_password, verify_password
        from src.domain.exceptions import ValidationError
        from src.data.database import get_session
        from src.data.orm_models import UserORM

        user = self.main.current_user
        if not user:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Редактировать профиль")
        dlg.setMinimumWidth(400)
        form = QFormLayout(dlg)

        full_name = QLineEdit(user.full_name or "")
        login = QLineEdit(user.login or "")

        old_password = QLineEdit()
        old_password.setPlaceholderText("Текущий пароль (если меняете)")
        old_password.setEchoMode(QLineEdit.Password)

        new_password = QLineEdit()
        new_password.setPlaceholderText("Новый пароль (оставьте пустым — не менять)")
        new_password.setEchoMode(QLineEdit.Password)

        form.addRow("ФИО:", full_name)
        form.addRow("Логин:", login)
        form.addRow("Текущий пароль:", old_password)
        form.addRow("Новый пароль:", new_password)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)

        if dlg.exec_() != QDialog.Accepted:
            return

        new_login = login.text().strip()
        new_name = full_name.text().strip()

        if not new_login or not new_name:
            self.main.show_error("ФИО и логин не могут быть пустыми.")
            return

        # Проверка занятости логина (если меняется)
        if new_login != user.login:
            existing = self.main.user_repo.get_by_login(new_login)
            if existing and existing.user_id != user.user_id:
                self.main.show_error("Логин уже занят.")
                return

        # Если меняется пароль — требуется ввести старый
        new_pwd_text = new_password.text().strip()
        new_pwd_hash = None
        if new_pwd_text:
            if not old_password.text():
                self.main.show_error("Для смены пароля введите текущий пароль.")
                return
            if not verify_password(old_password.text(), user.password_hash):
                self.main.show_error("Текущий пароль указан неверно.")
                return
            try:
                new_pwd_hash = hash_password(new_pwd_text)
            except ValidationError as e:
                self.main.show_error(str(e))
                return

        # Сохраняем в БД
        with get_session() as s:
            obj = s.get(UserORM, user.user_id)
            if not obj:
                self.main.show_error("Пользователь не найден в БД.")
                return
            obj.full_name = new_name
            obj.login = new_login
            if new_pwd_hash:
                obj.password_hash = new_pwd_hash
            s.commit()

        # Обновляем объект в памяти
        user.full_name = new_name
        user.login = new_login
        if new_pwd_hash:
            user.password_hash = new_pwd_hash

        self.main.show_info("Профиль обновлён.")
        self.refresh()

    def _reload_user(self):
        """Перечитывает объект пользователя из БД."""
        from src.data.database import get_session
        from src.data.orm_models import UserORM

        if not self.main.current_user:
            return
        with get_session() as s:
            fresh = s.get(UserORM, self.main.current_user.user_id)
            if fresh:
                self.main.current_user = fresh


    def _on_create_booking(self):
        dlg = BookingDialog(self.main)
        if dlg.exec_() == dlg.Accepted:
            self.refresh()

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)