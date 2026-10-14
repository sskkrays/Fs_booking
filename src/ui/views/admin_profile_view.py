"""Профиль администратора (Figma: 'Мой профиль (администратор)')."""

from datetime import datetime, timedelta
from decimal import Decimal

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import func, select

from src.data.database import get_session
from src.data.orm_models import BookingORM, HallORM, RoleORM
from src.ui.widgets.common import build_sidebar


class AdminProfileView(QWidget):
    """Панель администратора с KPI, задачами и фильтром периода."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.period = "month"
        self.sel_year = datetime.now().year
        self.sel_month = datetime.now().month
        self.sel_day = datetime.now().day
        self.sel_quarter = ((datetime.now().month - 1) // 3) + 1
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = build_sidebar(self.main, [
            ("Мой профиль", lambda: self.main.show_view(self)),
            ("Календарь", lambda: self.main.show_view(self.main.calendar_view)),
            ("Брони", lambda: self.main.show_view(self.main.booking_view)),
            ("Клиенты", lambda: self.main.show_view(self.main.clients_view)),
            ("Отчёты", lambda: self.main.show_view(self.main.reports_view)),
            ("Справочник", lambda: self.main.show_view(self.main.references_hub_view)),
        ])
        root.addWidget(sidebar)

        body = QVBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(14)

        # ---------- Компактная карточка профиля ----------
        card = QFrame()
        card.setStyleSheet(
            "background-color:#DCE9EF; border:1px solid #B7C9D3; "
            "border-radius:8px;"
        )
        card.setMaximumHeight(100)
        cl = QHBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 12)
        cl.setSpacing(16)

        info = QVBoxLayout()
        info.setSpacing(6)
        self.user_name = QLabel("—")
        self.user_name.setStyleSheet(
            "font-size:16pt; font-weight:bold; color:#2B2B2B; background:transparent;"
        )
        info.addWidget(self.user_name)

        self.user_phone = QLabel("+7 991 114 82 34")
        self.user_phone.setStyleSheet(
            "font-size:11pt; color:#2B2B2B; background:transparent; "
            "padding-left: 2px;"
        )
        info.addWidget(self.user_phone)
        info.addStretch()
        cl.addLayout(info)
        cl.addStretch()

        # Кнопка редактирования профиля
        edit_btn = QPushButton("Редактировать профиль")
        edit_btn.setFixedHeight(32)
        edit_btn.setStyleSheet(
            "QPushButton { background-color:#6F8E9E; color:white; "
            "border:none; border-radius:6px; padding:6px 14px; font-size:9pt; }"
            "QPushButton:hover { background-color:#5E7C8C; }"
        )
        edit_btn.clicked.connect(self._on_edit_profile)
        cl.addWidget(edit_btn)

        body.addWidget(card)

        # ---------- Фильтр периода ----------
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("Период:"))

        self.period_buttons = {}
        for key, label in (("month", "Месяц"), ("quarter", "Квартал"), ("year", "Год")):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, k=key: self._set_period(k))
            self.period_buttons[key] = btn
            filter_row.addWidget(btn)
        filter_row.addStretch()
        body.addLayout(filter_row)
        self._update_period_styles()

        # ---------- Основная зона: слева KPI, справа задачи ----------
        main_row = QHBoxLayout()
        main_row.setSpacing(14)

        # Левая колонка — выручка
        left_col = QVBoxLayout()

        revenue_card = QFrame()
        revenue_card.setStyleSheet(
            "background-color:#FDF6E3; border:1px solid #C8D4DA; "
            "border-radius:10px;"
        )
        revenue_card.setMinimumHeight(140)
        rc = QVBoxLayout(revenue_card)
        rc.setContentsMargins(20, 16, 20, 16)
        rc.setSpacing(10)

        revenue_title = QLabel("Выручка за период")
        revenue_title.setStyleSheet(
            "font-size:13pt; color:#2B2B2B; "
            "background:transparent;"
        )
        rc.addWidget(revenue_title)

        self.revenue_value = QLabel("0 ₽")
        self.revenue_value.setStyleSheet(
            "font-size:28pt; font-weight:bold; color:#2B2B2B; "
            "background:transparent;"
        )
        rc.addWidget(self.revenue_value)
        left_col.addWidget(revenue_card)
        left_col.addStretch()
        main_row.addLayout(left_col, stretch=1)

        # Правая колонка — задачи с прокруткой
        tasks_card = QFrame()
        tasks_card.setStyleSheet(
            "background-color:#FDF6E3; border:1px solid #C8D4DA; "
            "border-radius:10px;"
        )
        tc = QVBoxLayout(tasks_card)
        tc.setContentsMargins(16, 12, 16, 12)
        tc.setSpacing(8)

        title = QLabel("Ожидания решений")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(
            "font-size:15pt; font-weight:bold; color:#2B2B2B; "
            "padding: 6px 0;"
        )
        tc.addWidget(title)
        # Кнопка добавления задачи
        add_btn = QPushButton("+ Добавить задачу")
        add_btn.setFixedHeight(34)
        add_btn.setStyleSheet(
            "QPushButton { background-color:#6F8E9E; color:white; "
            "border:none; border-radius:8px; font-weight:bold; font-size:10pt; }"
            "QPushButton:hover { background-color:#5E7C8C; }"
        )
        add_btn.clicked.connect(self._on_add_task)
        tc.addWidget(add_btn)

        # Скролл для задач
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            "QScrollBar:vertical { width: 8px; background: #EAF2F5; }"
            "QScrollBar::handle:vertical { background: #B7C9D3; border-radius: 4px; }"
        )

        tasks_widget = QWidget()
        tasks_widget.setStyleSheet("background: transparent;")
        self.tasks_container = QVBoxLayout(tasks_widget)
        self.tasks_container.setSpacing(6)
        self.tasks_container.setContentsMargins(0, 0, 8, 0)
        self.tasks_container.addStretch()

        scroll.setWidget(tasks_widget)
        tc.addWidget(scroll, stretch=1)

        main_row.addWidget(tasks_card, stretch=1)
        body.addLayout(main_row)

        container = QWidget()
        container.setLayout(body)
        root.addWidget(container, stretch=1)

    # ---------- Работа с профилем ----------

    def _on_edit_profile(self):
        """Диалог редактирования профиля администратора."""
        user = self.main.current_user
        if not user:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Редактировать профиль")
        dlg.setMinimumWidth(400)
        form = QFormLayout(dlg)

        full_name = QLineEdit(user.full_name or "")
        login = QLineEdit(user.login or "")
        login.setReadOnly(True)

        phone = QLineEdit(getattr(user, "phone", "") or "")
        phone.setPlaceholderText("+79919876056 или 89919876056")

        new_password = QLineEdit()
        new_password.setPlaceholderText("Оставьте пустым, если не хотите менять")
        new_password.setEchoMode(QLineEdit.Password)

        form.addRow("ФИО:", full_name)
        form.addRow("Логин:", login)
        form.addRow("Телефон:", phone)
        form.addRow("Новый пароль:", new_password)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)

        if dlg.exec_() == QDialog.Accepted:
            from src.domain.services import hash_password, normalize_phone
            from src.domain.exceptions import ValidationError

            # Нормализация телефона
            phone_raw = phone.text().strip()
            phone_normalized = ""
            if phone_raw:
                try:
                    phone_normalized = normalize_phone(phone_raw)
                except ValidationError as e:
                    self.main.show_error(str(e))
                    return

            with get_session() as s:
                obj = s.get(type(user), user.user_id)
                if obj:
                    obj.full_name = full_name.text().strip() or obj.full_name
                    if phone_normalized:
                        obj.phone = phone_normalized
                    if new_password.text().strip():
                        obj.password_hash = hash_password(new_password.text())
                    s.commit()

            user.full_name = full_name.text().strip() or user.full_name
            user.phone = phone_normalized or getattr(user, "phone", "")
            self.main.show_info("Профиль обновлён.")
            self.refresh()

    # ---------- Работа с периодом ----------

    def _set_period(self, key):
        """Переключает период с диалогом выбора даты."""
        self.period = key

        if key == "month":
            if not self._select_month():
                return
        elif key == "quarter":
            if not self._select_quarter():
                return
        elif key == "year":
            if not self._select_year():
                return

        self._update_period_styles()
        self.refresh()

    def _select_month(self):
        """Диалог выбора месяца и года."""
        months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        years = [str(y) for y in range(datetime.now().year - 3, datetime.now().year + 2)]

        dlg = QDialog(self)
        dlg.setWindowTitle("Выбор месяца")
        dlg.setMinimumWidth(280)
        form = QFormLayout(dlg)

        month_combo = QComboBox()
        month_combo.addItems(months)
        month_combo.setCurrentIndex(self.sel_month - 1)

        year_combo = QComboBox()
        year_combo.addItems(years)
        year_combo.setCurrentText(str(self.sel_year))

        form.addRow("Месяц:", month_combo)
        form.addRow("Год:", year_combo)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)

        if dlg.exec_() != QDialog.Accepted:
            return False
        self.sel_month = month_combo.currentIndex() + 1
        self.sel_year = int(year_combo.currentText())
        return True

    def _select_quarter(self):
        """Диалог выбора квартала и года."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Выбор квартала")
        dlg.setMinimumWidth(280)
        form = QFormLayout(dlg)

        quarter_combo = QComboBox()
        quarter_combo.addItems(["I квартал", "II квартал", "III квартал", "IV квартал"])
        quarter_combo.setCurrentIndex(self.sel_quarter - 1)

        years = [str(y) for y in range(datetime.now().year - 3, datetime.now().year + 2)]
        year_combo = QComboBox()
        year_combo.addItems(years)
        year_combo.setCurrentText(str(self.sel_year))

        form.addRow("Квартал:", quarter_combo)
        form.addRow("Год:", year_combo)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)

        if dlg.exec_() != QDialog.Accepted:
            return False
        self.sel_quarter = quarter_combo.currentIndex() + 1
        self.sel_year = int(year_combo.currentText())
        return True

    def _select_year(self):
        """Диалог выбора года."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Выбор года")
        dlg.setMinimumWidth(280)
        form = QFormLayout(dlg)

        years = [str(y) for y in range(datetime.now().year - 5, datetime.now().year + 2)]
        year_combo = QComboBox()
        year_combo.addItems(years)
        year_combo.setCurrentText(str(self.sel_year))

        form.addRow("Год:", year_combo)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)

        if dlg.exec_() != QDialog.Accepted:
            return False
        self.sel_year = int(year_combo.currentText())
        return True

    def _select_month(self):
        """Диалог выбора дня, месяца и года."""
        months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        years = [str(y) for y in range(datetime.now().year - 3, datetime.now().year + 2)]
        days = [str(d) for d in range(1, 32)]

        dlg = QDialog(self)
        dlg.setWindowTitle("Выбор даты")
        dlg.setMinimumWidth(280)
        form = QFormLayout(dlg)

        day_combo = QComboBox()
        day_combo.addItems(days)
        day_combo.setCurrentText(str(self.sel_day))

        month_combo = QComboBox()
        month_combo.addItems(months)
        month_combo.setCurrentIndex(self.sel_month - 1)

        year_combo = QComboBox()
        year_combo.addItems(years)
        year_combo.setCurrentText(str(self.sel_year))

        form.addRow("День:", day_combo)
        form.addRow("Месяц:", month_combo)
        form.addRow("Год:", year_combo)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)

        if dlg.exec_() != QDialog.Accepted:
            return False

        self.sel_day = int(day_combo.currentText())
        self.sel_month = month_combo.currentIndex() + 1
        self.sel_year = int(year_combo.currentText())
        return True

    def _select_year(self):
        """Диалог выбора года."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Выбор года")
        dlg.setMinimumWidth(260)
        form = QFormLayout(dlg)

        years = [str(y) for y in range(datetime.now().year - 5, datetime.now().year + 2)]
        year_combo = QComboBox()
        year_combo.addItems(years)
        year_combo.setCurrentText(str(self.sel_year))

        form.addRow("Год:", year_combo)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)

        if dlg.exec_() != QDialog.Accepted:
            return False
        self.sel_year = int(year_combo.currentText())
        return True

    def _update_period_styles(self):
        labels = {
            "month": f"{self.sel_day:02d}.{self.sel_month:02d}.{self.sel_year}",
            "quarter": f"{self.sel_quarter} кв. {self.sel_year}",
            "year": str(self.sel_year),
        }
        for k, btn in self.period_buttons.items():
            btn.setText(labels[k])
            if k == self.period:
                btn.setStyleSheet(
                    "QPushButton { background-color:#6F8E9E; color:white; "
                    "border:1px solid #5E7C8C; border-radius:6px; "
                    "padding:8px 16px; font-size:10pt; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background-color:#FDF6E3; color:#2B2B2B; "
                    "border:1px solid #C8D4DA; border-radius:6px; "
                    "padding:8px 16px; font-size:10pt; }"
                    "QPushButton:hover { background-color:#E8D9B8; }"
                )

    def _period_range(self):
        """Возвращает (start, end) — границы выбранного периода."""
        if self.period == "month":
            # Начало — выбранный день
            start = datetime(self.sel_year, self.sel_month, self.sel_day, 0, 0, 0)
            # Конец — конец месяца
            if self.sel_month == 12:
                end = datetime(self.sel_year, 12, 31, 23, 59, 59)
            else:
                end = datetime(self.sel_year, self.sel_month + 1, 1) - timedelta(seconds=1)
        elif self.period == "quarter":
            q_month = (self.sel_quarter - 1) * 3 + 1
            start = datetime(self.sel_year, q_month, 1, 0, 0, 0)
            end_month = q_month + 2
            if end_month == 12:
                end = datetime(self.sel_year, 12, 31, 23, 59, 59)
            else:
                end = datetime(self.sel_year, end_month + 1, 1) - timedelta(seconds=1)
        else:
            start = datetime(self.sel_year, 1, 1, 0, 0, 0)
            end = datetime(self.sel_year, 12, 31, 23, 59, 59)
        return start, end

    # ---------- Работа с задачами ----------

    def _reload_tasks(self):
        """Перерисовывает список задач из БД."""
        while self.tasks_container.count():
            item = self.tasks_container.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        tasks = self.main.task_repo.list_all()
        for task in tasks:
            self.tasks_container.addWidget(
                self._make_task_row(task.task_id, task.text)
            )
        self.tasks_container.addStretch()

    def _make_task_row(self, task_id, text):
        """Одна компактная строка задачи."""
        row = QFrame()
        row.setStyleSheet(
            "background-color:#FFFFFF; border:1px solid #C8D4DA; border-radius:8px;"
        )
        row.setMaximumHeight(56)
        h = QHBoxLayout(row)
        h.setContentsMargins(12, 6, 8, 6)
        h.setSpacing(8)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("color:#2B2B2B; font-size:11pt; background:transparent;")
        h.addWidget(label, stretch=1)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(26, 26)
        del_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #C97B7B;"
            "  color: white;"
            "  border: none;"
            "  border-radius: 13px;"
            "  font-weight: bold;"
            "  font-size: 11pt;"
            "  padding: 0;"
            "  text-align: center;"
            "}"
            "QPushButton:hover { background-color: #A85F5F; }"
        )
        del_btn.clicked.connect(lambda _, tid=task_id: self._on_delete_task(tid))
        h.addWidget(del_btn)

        return row

    def _on_add_task(self):
        """Диалог добавления задачи."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Новая задача")
        dlg.setMinimumWidth(400)
        form = QFormLayout(dlg)

        text_input = QLineEdit()
        text_input.setPlaceholderText("Что нужно сделать?")
        form.addRow("Текст:", text_input)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)

        if dlg.exec_() == QDialog.Accepted:
            text = text_input.text().strip()
            if not text:
                self.main.show_error("Введите текст задачи.")
                return
            self.main.task_repo.create(text)
            self._reload_tasks()

    def _on_delete_task(self, task_id):
        """Удаляет задачу."""
        if self.main.task_repo.delete(task_id):
            self._reload_tasks()

    # ---------- Обновление данных ----------

    def refresh(self):
        """Обновляет профиль, выручку, задачи."""
        user = self.main.current_user
        if user:
            self.user_name.setText(user.full_name or "—")
            phone = getattr(user, "phone", "") or "+7 991 114 82 34"
            self.user_phone.setText(phone)

        start, end = self._period_range()

        with get_session() as s:
            total = s.scalar(
                select(func.coalesce(func.sum(BookingORM.total_price), 0)).where(
                    BookingORM.start_datetime >= start,
                    BookingORM.start_datetime <= end,
                )
            ) or 0
        self.revenue_value.setText(f"{Decimal(total):.2f} ₽")

        self._reload_tasks()

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)