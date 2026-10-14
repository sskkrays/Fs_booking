"""CRUD клиентов (Figma: 'Клиенты')."""

from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.domain.exceptions import ValidationError
from src.domain.services import normalize_phone
from src.ui.widgets.common import build_topbar, make_button, make_table


class ClientsView(QWidget):
    """Экран «Клиенты»."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(10)

        root.addLayout(build_topbar(self.main, "Клиенты"))

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по имени...")
        top.addWidget(self.search)
        top.addWidget(make_button("Найти", self.refresh, accent=True))
        top.addWidget(make_button("+ Добавить", self._on_add))
        top.addWidget(make_button("Удалить", self._on_delete, danger=True))
        root.addLayout(top)

        self.table = make_table(["ID", "Имя", "Телефон", "Email", "Заметки"])
        root.addWidget(self.table, stretch=1)

    def refresh(self):
        clients = self.main.client_repo.list_all(search=self.search.text().strip())
        self.table.setRowCount(len(clients))
        for i, c in enumerate(clients):
            for j, v in enumerate([
                str(c.client_id), c.name, c.phone, c.email, c.notes or ""
            ]):
                self.table.setItem(i, j, QTableWidgetItem(v))

    def _on_add(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Новый клиент")
        form = QFormLayout(dlg)

        name = QLineEdit()
        phone = QLineEdit()
        email = QLineEdit()
        notes = QLineEdit()
        form.addRow("Имя:", name)
        form.addRow("Телефон:", phone)
        form.addRow("Email:", email)
        form.addRow("Заметки:", notes)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)

        if dlg.exec_() == QDialog.Accepted and name.text().strip():
            try:
                phone_normalized = normalize_phone(phone.text())
            except ValidationError as e:
                self.main.show_error(str(e))
                return

            self.main.client_repo.create(
                name.text().strip(),
                phone_normalized,
                email.text(),
                notes.text(),
            )
            self.refresh()

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            self.main.show_error("Выберите клиента.")
            return
        client_id = int(self.table.item(row, 0).text())
        if self.main.client_repo.delete(client_id):
            self.main.show_info("Клиент удалён.")
            self.refresh()

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)