"""Главное окно приложения FS.Booking."""

from PyQt5.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from src.data.repositories import (
    BookingRepository,
    ClientRepository,
    EquipmentRepository,
    HallRepository,
    StatusRepository,
    TaskRepository,
    UserRepository,
)
from src.ui.style import APP_STYLE
from src.ui.views.admin_profile_view import AdminProfileView
from src.ui.views.booking_view import BookingView
from src.ui.views.calendar_view import CalendarView
from src.ui.views.client_profile_view import ClientProfileView
from src.ui.views.clients_view import ClientsView
from src.ui.views.forgot_view import ForgotView
from src.ui.views.login_view import LoginView
from src.ui.views.references_hub_view import ReferencesHubView
from src.ui.views.register_view import RegisterView
from src.ui.views.reports_view import ReportsView


class MainWindow(QMainWindow):
    """Главное окно приложения с навигацией через QStackedWidget."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FS.Booking")
        self.resize(1150, 720)
        self.setStyleSheet(APP_STYLE)

        self.user_repo = UserRepository()
        self.client_repo = ClientRepository()
        self.hall_repo = HallRepository()
        self.equipment_repo = EquipmentRepository()
        self.status_repo = StatusRepository()
        self.booking_repo = BookingRepository()
        self.task_repo = TaskRepository()

        self.current_user = None
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.login_view = LoginView(self)
        self.register_view = RegisterView(self)
        self.forgot_view = ForgotView(self)
        self.client_profile_view = ClientProfileView(self)
        self.admin_profile_view = AdminProfileView(self)
        self.calendar_view = CalendarView(self)
        self.booking_view = BookingView(self)
        self.clients_view = ClientsView(self)
        self.reports_view = ReportsView(self)
        self.references_hub_view = ReferencesHubView(self)

        for w in (
            self.login_view, self.register_view, self.forgot_view,
            self.client_profile_view, self.admin_profile_view,
            self.calendar_view, self.booking_view, self.clients_view,
            self.reports_view, self.references_hub_view,
        ):
            self.stack.addWidget(w)

        self.show_login()

    def show_login(self):
        self.stack.setCurrentWidget(self.login_view)

    def show_register(self):
        self.stack.setCurrentWidget(self.register_view)

    def show_forgot(self):
        self.stack.setCurrentWidget(self.forgot_view)

    def show_dashboard(self):
        role = self.current_user.role.name.lower() if self.current_user else ""
        if "админ" in role or "admin" in role:
            self.stack.setCurrentWidget(self.admin_profile_view)
        else:
            self.stack.setCurrentWidget(self.client_profile_view)

    def show_view(self, view):
        self.stack.setCurrentWidget(view)

    def logout(self):
        self.current_user = None
        self.show_login()

    def show_error(self, text):
        QMessageBox.warning(self, "Ошибка", text)

    def show_info(self, text):
        QMessageBox.information(self, "Информация", text)