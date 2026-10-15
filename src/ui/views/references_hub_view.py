"""Объединённый справочник с вкладками: Залы, Оборудование, Статус, Пользователи."""

from decimal import Decimal

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import select

from src.data.database import get_session
from src.data.orm_models import (
    BookingORM,
    EquipmentORM,
    HallORM,
    UserORM,
)
from src.ui.widgets.common import build_sidebar, make_button, make_table


class ReferencesHubView(QWidget):
    """Объединённый справочник с 4 вкладками."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.current_tab = "halls"
        self._build()
        self._switch_tab("halls")

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = build_sidebar(self.main, [
            ("Мой профиль", lambda: self.main.show_view(self.main.admin_profile_view)),
            ("Календарь", lambda: self.main.show_view(self.main.calendar_view)),
            ("Брони", lambda: self.main.show_view(self.main.booking_view)),
            ("Клиенты", lambda: self.main.show_view(self.main.clients_view)),
            ("Отчёты", lambda: self.main.show_view(self.main.reports_view)),
            ("Справочник", lambda: self.main.show_view(self)),
        ])
        root.addWidget(sidebar)

        body = QVBoxLayout()
        body.setContentsMargins(20, 20, 20, 20)
        body.setSpacing(14)

        # Строка вкладок
        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(8)

        self.tabs = {}
        for key, label in (
            ("halls", "Залы"),
            ("equipment", "Оборудование"),
            ("statuses", "Статус"),
            ("users", "Пользователи"),
        ):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, k=key: self._switch_tab(k))
            self.tabs[key] = btn
            tabs_row.addWidget(btn)

        tabs_row.addStretch()

        self.add_btn = QPushButton("+ Добавить")
        self.add_btn.setStyleSheet(
            "QPushButton { background-color:#FDF6E3; color:#2B2B2B; "
            "border:1px solid #C8D4DA; border-radius:14px; padding:6px 14px; }"
        )
        self.add_btn.clicked.connect(self._on_add_click)
        tabs_row.addWidget(self.add_btn)

        body.addLayout(tabs_row)

        # Стек страниц
        self.stack = QStackedWidget()
        body.addWidget(self.stack, stretch=1)

        self.pages = {}
        self.pages["halls"] = self._make_halls_page()
        self.pages["equipment"] = self._make_equipment_page()
        self.pages["statuses"] = self._make_statuses_page()
        self.pages["users"] = self._make_users_page()

        for key in ("halls", "equipment", "statuses", "users"):
            self.stack.addWidget(self.pages[key])

        container = QWidget()
        container.setLayout(body)
        root.addWidget(container, stretch=1)

    # ---------- Страницы ----------

    def _make_halls_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.halls_table = make_table(
            ["ID", "Название", "Описание", "Цена/час", "Статус", "Действия"]
        )
        self.halls_table.setColumnWidth(5, 240)
        layout.addWidget(self.halls_table, stretch=1)
        return page

    def _make_equipment_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.equipment_table = make_table(
            ["ID", "Название", "Категория", "Цена/день", "Доступно", "Действия"]
        )
        self.equipment_table.setColumnWidth(5, 240)
        layout.addWidget(self.equipment_table, stretch=1)
        return page

    def _make_statuses_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.statuses_table = make_table(
            ["ID", "Зал", "Тип", "Тек. статус", "Дата", "Действия"]
        )
        self.statuses_table.setColumnWidth(5, 240)
        layout.addWidget(self.statuses_table, stretch=1)
        return page

    def _make_users_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.users_table = make_table(
            ["ID", "ФИО", "Логин", "Роль", "Действия"]
        )
        self.users_table.setColumnWidth(4, 240)
        layout.addWidget(self.users_table, stretch=1)
        return page

    # ---------- Переключение вкладок ----------

    def _switch_tab(self, key):
        self.current_tab = key
        self.stack.setCurrentWidget(self.pages[key])

        labels = {
            "halls": "+ Добавить зал",
            "equipment": "+ Добавить оборудование",
            "statuses": "Статус брони",
            "users": "+ Добавить пользователя",
        }
        self.add_btn.setText(labels[key])

        for tab_key, btn in self.tabs.items():
            if tab_key == key:
                btn.setStyleSheet(
                    "QPushButton { background-color:#6F8E9E; color:white; "
                    "border:1px solid #5E7C8C; border-radius:14px; padding:6px 14px; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background-color:#FDF6E3; color:#2B2B2B; "
                    "border:1px solid #C8D4DA; border-radius:14px; padding:6px 14px; }"
                )

        self._refresh_current_tab()

    def _refresh_current_tab(self):
        if self.current_tab == "halls":
            self._refresh_halls()
        elif self.current_tab == "equipment":
            self._refresh_equipment()
        elif self.current_tab == "statuses":
            self._refresh_statuses()
        elif self.current_tab == "users":
            self._refresh_users()

    # ---------- Заполнение ----------

    def _refresh_halls(self):
        rows = self.main.hall_repo.list_all()
        self.halls_table.setRowCount(len(rows))
        for i, h in enumerate(rows):
            status = "Активен" if h.is_active else "Не активен"
            values = [
                str(h.hall_id),
                h.name,
                h.description or "—",
                f"{h.price_per_hour} ₽",
                status,
            ]
            for j, v in enumerate(values):
                self.halls_table.setItem(i, j, QTableWidgetItem(v))
            self.halls_table.setCellWidget(
                i, 5, self._make_action_buttons(
                    h.hall_id, self._edit_hall, self._delete_hall
                )
            )

    def _refresh_equipment(self):
        rows = self.main.equipment_repo.list_all()
        self.equipment_table.setRowCount(len(rows))
        for i, e in enumerate(rows):
            status = "Активен" if e.is_available else "Не активен"
            values = [
                str(e.equipment_id),
                e.name,
                e.category or "—",
                f"{e.price_per_day} ₽",
                status,
            ]
            for j, v in enumerate(values):
                self.equipment_table.setItem(i, j, QTableWidgetItem(v))
            self.equipment_table.setCellWidget(
                i, 5, self._make_action_buttons(
                    e.equipment_id, self._edit_equipment, self._delete_equipment
                )
            )

    def _refresh_statuses(self):
        rows = self.main.booking_repo.list_all()
        self.statuses_table.setRowCount(len(rows))
        for i, b in enumerate(rows):
            values = [
                str(b.booking_id),
                b.hall.name if b.hall else "—",
                "Бронь",
                b.status.name if b.status else "—",
                b.start_datetime.strftime("%d.%m.%Y") if b.start_datetime else "—",
            ]
            for j, v in enumerate(values):
                self.statuses_table.setItem(i, j, QTableWidgetItem(v))
            self.statuses_table.setCellWidget(
                i, 5, self._make_action_buttons(
                    b.booking_id, self._edit_status, self._delete_status
                )
            )

    def _refresh_users(self):
        rows = self.main.user_repo.list_all()
        self.users_table.setRowCount(len(rows))
        for i, u in enumerate(rows):
            values = [
                str(u.user_id),
                u.full_name or "—",
                u.login,
                u.role.name if u.role else "—",
            ]
            for j, v in enumerate(values):
                self.users_table.setItem(i, j, QTableWidgetItem(v))
            self.users_table.setCellWidget(
                i, 4, self._make_action_buttons(
                    u.user_id, self._edit_user, self._delete_user
                )
            )

    def _make_action_buttons(self, obj_id, on_edit, on_delete):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        edit_btn = QPushButton("Изменить")
        edit_btn.setFixedSize(100, 28)
        edit_btn.setStyleSheet(
            "QPushButton { background-color:#B7C9D3; color:#2B2B2B; "
            "border:1px solid #8FA8B5; border-radius:4px; font-size:9pt; }"
        )
        edit_btn.clicked.connect(lambda _, oid=obj_id: on_edit(oid))
        layout.addWidget(edit_btn)

        del_btn = QPushButton("Удалить")
        del_btn.setFixedSize(100, 28)
        del_btn.setStyleSheet(
            "QPushButton { background-color:#C97B7B; color:white; "
            "border:none; border-radius:4px; font-size:9pt; }"
        )
        del_btn.clicked.connect(lambda _, oid=obj_id: on_delete(oid))
        layout.addWidget(del_btn)

        return widget

    # ---------- Действия ----------

    def _on_add_click(self):
        if self.current_tab == "halls":
            self._add_hall()
        elif self.current_tab == "equipment":
            self._add_equipment()
        else:
            self.main.show_info("Добавление через соответствующий раздел.")

    def _add_hall(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Новый зал")
        form = QFormLayout(dlg)
        name = QLineEdit()
        desc = QLineEdit()
        price = QLineEdit()
        form.addRow("Название:", name)
        form.addRow("Описание:", desc)
        form.addRow("Цена/час:", price)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec_() == QDialog.Accepted and name.text().strip():
            try:
                self.main.hall_repo.create(
                    name.text().strip(), desc.text(), Decimal(price.text() or "0")
                )
                self._refresh_halls()
            except Exception as e:
                self.main.show_error(f"Ошибка: {e}")

    def _add_equipment(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Новое оборудование")
        form = QFormLayout(dlg)
        name = QLineEdit()
        cat = QLineEdit()
        price = QLineEdit()
        form.addRow("Название:", name)
        form.addRow("Категория:", cat)
        form.addRow("Цена/день:", price)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec_() == QDialog.Accepted and name.text().strip():
            try:
                self.main.equipment_repo.create(
                    name.text().strip(), cat.text(), Decimal(price.text() or "0")
                )
                self._refresh_equipment()
            except Exception as e:
                self.main.show_error(f"Ошибка: {e}")

    def _edit_hall(self, hall_id):
        for h in self.main.hall_repo.list_all():
            if h.hall_id == hall_id:
                dlg = QDialog(self)
                dlg.setWindowTitle(f"Зал #{hall_id}")
                form = QFormLayout(dlg)
                name = QLineEdit(h.name)
                desc = QLineEdit(h.description or "")
                price = QLineEdit(str(h.price_per_hour))
                form.addRow("Название:", name)
                form.addRow("Описание:", desc)
                form.addRow("Цена/час:", price)
                bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                bb.accepted.connect(dlg.accept)
                bb.rejected.connect(dlg.reject)
                form.addRow(bb)
                if dlg.exec_() == QDialog.Accepted:
                    with get_session() as s:
                        obj = s.get(HallORM, hall_id)
                        if obj:
                            obj.name = name.text().strip() or obj.name
                            obj.description = desc.text()
                            obj.price_per_hour = Decimal(price.text() or "0")
                            s.commit()
                    self._refresh_halls()
                return

    def _edit_equipment(self, equipment_id):
        for e in self.main.equipment_repo.list_all():
            if e.equipment_id == equipment_id:
                dlg = QDialog(self)
                dlg.setWindowTitle(f"Оборудование #{equipment_id}")
                form = QFormLayout(dlg)
                name = QLineEdit(e.name)
                cat = QLineEdit(e.category or "")
                price = QLineEdit(str(e.price_per_day))
                avail = QComboBox()
                avail.addItem("Активен", True)
                avail.addItem("Не активен", False)
                avail.setCurrentIndex(0 if e.is_available else 1)
                form.addRow("Название:", name)
                form.addRow("Категория:", cat)
                form.addRow("Цена/день:", price)
                form.addRow("Доступно:", avail)
                bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                bb.accepted.connect(dlg.accept)
                bb.rejected.connect(dlg.reject)
                form.addRow(bb)
                if dlg.exec_() == QDialog.Accepted:
                    with get_session() as s:
                        obj = s.get(EquipmentORM, equipment_id)
                        if obj:
                            obj.name = name.text().strip() or obj.name
                            obj.category = cat.text()
                            obj.price_per_day = Decimal(price.text() or "0")
                            obj.is_available = avail.currentData()
                            s.commit()
                    self._refresh_equipment()
                return

    def _edit_status(self, booking_id):
        statuses = self.main.status_repo.list_all()
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Статус брони #{booking_id}")
        form = QFormLayout(dlg)
        combo = QComboBox()
        for st in statuses:
            combo.addItem(st.name, st.status_id)
        form.addRow("Новый статус:", combo)
        url = QLineEdit()
        url.setPlaceholderText("Ссылка на фото (необязательно)")
        form.addRow("Фото:", url)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec_() == QDialog.Accepted:
            with get_session() as s:
                obj = s.get(BookingORM, booking_id)
                if obj:
                    obj.status_id = combo.currentData()
                    if url.text().strip():
                        obj.photo_url = url.text().strip()
                    s.commit()
            self._refresh_statuses()

    def _edit_user(self, user_id):
        for u in self.main.user_repo.list_all():
            if u.user_id == user_id:
                dlg = QDialog(self)
                dlg.setWindowTitle(f"Пользователь #{user_id}")
                form = QFormLayout(dlg)
                full_name = QLineEdit(u.full_name or "")
                form.addRow("ФИО:", full_name)
                bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                bb.accepted.connect(dlg.accept)
                bb.rejected.connect(dlg.reject)
                form.addRow(bb)
                if dlg.exec_() == QDialog.Accepted:
                    with get_session() as s:
                        obj = s.get(UserORM, user_id)
                        if obj:
                            obj.full_name = full_name.text().strip() or obj.full_name
                            s.commit()
                    self._refresh_users()
                return

    def _delete_hall(self, hall_id):
        if self.main.hall_repo.delete(hall_id):
            self._refresh_halls()

    def _delete_equipment(self, equipment_id):
        if self.main.equipment_repo.delete(equipment_id):
            self._refresh_equipment()

    def _delete_status(self, booking_id):
        if self.main.booking_repo.delete(booking_id):
            self._refresh_statuses()

    def _delete_user(self, user_id):
        if self.main.user_repo.delete(user_id):
            self._refresh_users()

    def showEvent(self, event):
        self._refresh_current_tab()
        super().showEvent(event)