"""
FS.Booking — приложение для бронирования залов.
Демонстрирует: Clean Code, MVC, SQLAlchemy ORM, PyQt5 UI, docstrings, тесты.

Запуск: python fs_booking.py
"""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox,
    QFormLayout, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String,
    create_engine, func, select,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# =====================================================================
# DOMAIN LAYER — бизнес-логика, не зависит ни от БД, ни от UI
# =====================================================================

class DomainError(Exception):
    """Базовое доменное исключение."""


class InvalidBookingPeriodError(DomainError):
    """Окончание брони раньше начала."""


class ValidationError(DomainError):
    """Некорректные входные данные."""


PBKDF2_ITERATIONS = 120_000


import re

def normalize_phone(raw: str) -> str:
    """
    Приводит телефон к единому формату +7XXXXXXXXXX.

    Допускаются только два формата на входе:
        +79911148234
        89911148235

    Args:
        raw: строка с телефоном от пользователя.

    Returns:
        Телефон в виде '+7XXXXXXXXXX'.

    Raises:
        ValidationError: если формат не подходит.
    """
    phone = (raw or "").strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    # Вариант +7XXXXXXXXXX — ровно 11 цифр, начинается с +7
    if re.fullmatch(r"\+7\d{10}", phone):
        return phone

    # Вариант 8XXXXXXXXXX — 11 цифр, начинается с 8 → заменяем на +7
    if re.fullmatch(r"8\d{10}", phone):
        return "+7" + phone[1:]

    raise ValidationError(
        "Неверный формат телефона. Допустимо: +79911148234 или 89911148235"
    )


def verify_password(password: str, stored: str) -> bool:
    """
    Проверяет пароль против сохранённого хеша.

    Args:
        password: введённый пароль.
        stored: хеш из БД.

    Returns:
        True, если пароль совпадает.
    """
    try:
        salt_hex, hash_hex = stored.split("$")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return digest.hex() == hash_hex


def calculate_booking_price(
    start: datetime,
    end: datetime,
    price_per_hour: Decimal,
    equipment_daily_prices: list[Decimal] | None = None,
) -> Decimal:
    """
    Рассчитывает стоимость бронирования.

    Args:
        start: начало брони.
        end: конец брони.
        price_per_hour: цена зала за час.
        equipment_daily_prices: суточные цены оборудования.

    Returns:
        Decimal с округлением до 2 знаков.

    Raises:
        InvalidBookingPeriodError: если end <= start.
    """
    if end <= start:
        raise InvalidBookingPeriodError("Окончание должно быть позже начала.")
    hours = Decimal((end - start).total_seconds()) / Decimal(3600)
    total = hours * Decimal(price_per_hour)
    if equipment_daily_prices:
        total += sum(equipment_daily_prices, Decimal("0"))
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def hash_password(password: str) -> str:
    """
    Хеширует пароль через PBKDF2-HMAC-SHA256.

    Args:
        password: пароль в открытом виде.

    Returns:
        Строка формата '<salt_hex>$<hash_hex>'.
    """
    if not password:
        raise ValidationError("Пароль не может быть пустым.")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """
    Проверяет пароль против сохранённого хеша.

    Args:
        password: введённый пароль.
        stored: строка из БД формата '<salt_hex>$<hash_hex>'.

    Returns:
        True, если пароль совпадает.
    """
    try:
        salt_hex, hash_hex = stored.split("$")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return digest.hex() == hash_hex


# =====================================================================
# DATA LAYER — SQLAlchemy ORM по ER-диаграмме
# =====================================================================

Base = declarative_base()


def _get_db_path() -> str:
    """
    Возвращает абсолютный путь к файлу базы данных.

    Логика:
    - Если приложение запущено из exe (PyInstaller) — база кладётся рядом с exe.
    - Если из исходников (python fs_booking.py) — рядом с файлом fs_booking.py.
    """
    import sys
    from pathlib import Path

    if getattr(sys, "frozen", False):
        # Запуск из exe (PyInstaller)
        base_dir = Path(sys.executable).parent
    else:
        # Запуск из исходников
        base_dir = Path(__file__).resolve().parent

    return str(base_dir / "fs_booking.db")


_db_path = _get_db_path()
engine = create_engine(f"sqlite:///{_db_path}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session():
    """Возвращает новую сессию SQLAlchemy."""
    return SessionLocal()


class RoleORM(Base):
    """Роль пользователя."""
    __tablename__ = "role"
    role_id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    description = Column(String(200))


class UserORM(Base):
    """Пользователь системы."""
    __tablename__ = "user"
    user_id = Column(Integer, primary_key=True)
    role_id = Column(Integer, ForeignKey("role.role_id"), nullable=False)
    login = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=False)
    role = relationship("RoleORM")


class ClientORM(Base):
    """Клиент."""
    __tablename__ = "client"
    client_id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    phone = Column(String(20))
    email = Column(String(100))
    notes = Column(String(500))


class HallORM(Base):
    """Зал для аренды."""
    __tablename__ = "hall"
    hall_id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(String(500))
    price_per_hour = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, default=True)


class StatusORM(Base):
    """Статус брони."""
    __tablename__ = "status"
    status_id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)


class BookingORM(Base):
    """Бронирование зала."""
    __tablename__ = "booking"
    booking_id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("client.client_id"), nullable=False)
    hall_id = Column(Integer, ForeignKey("hall.hall_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("user.user_id"), nullable=False)
    start_datetime = Column(DateTime, nullable=False)
    end_datetime = Column(DateTime, nullable=False)
    status_id = Column(Integer, ForeignKey("status.status_id"), nullable=False)
    total_price = Column(Numeric(10, 2), nullable=False)
    client = relationship("ClientORM")
    hall = relationship("HallORM")
    status = relationship("StatusORM")


class EquipmentORM(Base):
    """Оборудование."""
    __tablename__ = "equipment"
    equipment_id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50))
    price_per_day = Column(Numeric(10, 2), nullable=False)
    is_available = Column(Boolean, default=True)


class BookingEquipmentORM(Base):
    """Связь брони и оборудования (M:N)."""
    __tablename__ = "booking_equipment"
    booking_equipment_id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("booking.booking_id"))
    equipment_id = Column(Integer, ForeignKey("equipment.equipment_id"))
    quantity = Column(Integer, default=1)


class PaymentORM(Base):
    """Платёж по брони."""
    __tablename__ = "payment"
    payment_id = Column(Integer, primary_key=True)
    booking_id = Column(Integer, ForeignKey("booking.booking_id"))
    amount = Column(Numeric(10, 2), nullable=False)
    payment_date = Column(DateTime, nullable=False)
    payment_method = Column(String(50))

class TaskORM(Base):
    """Задача/напоминание для панели администратора."""
    __tablename__ = "task"
    task_id = Column(Integer, primary_key=True)
    text = Column(String(500), nullable=False)
    is_done = Column(Boolean, default=False)


# ---------- Репозитории (CRUD) ----------

class ClientRepository:
    """CRUD для клиентов. Все запросы — через ORM, SQL-инъекции невозможны."""

    def create(self, name: str, phone: str, email: str, notes: str = "") -> ClientORM:
        """Создаёт клиента."""
        with get_session() as s:
            obj = ClientORM(name=name, phone=phone, email=email, notes=notes)
            s.add(obj); s.commit(); s.refresh(obj)
            return obj

    def list_all(self, search: str = "") -> list[ClientORM]:
        """Возвращает список клиентов с регистронезависимым поиском по имени (Python-фильтр)."""
        with get_session() as s:
            stmt = select(ClientORM).order_by(ClientORM.name)
            all_clients = list(s.scalars(stmt).all())

        # Фильтрация на стороне Python — работает с кириллицей без проблем
        if search:
            needle = search.strip().lower()
            all_clients = [c for c in all_clients if needle in (c.name or "").lower()]

        return all_clients

    def get(self, client_id: int) -> ClientORM | None:
        """Возвращает клиента по ID."""
        with get_session() as s:
            return s.get(ClientORM, client_id)

    def update(self, client_id: int, **fields) -> ClientORM | None:
        """Обновляет разрешённые поля клиента."""
        allowed = {"name", "phone", "email", "notes"}
        with get_session() as s:
            obj = s.get(ClientORM, client_id)
            if not obj:
                return None
            for k, v in fields.items():
                if k in allowed:
                    setattr(obj, k, v)
            s.commit(); s.refresh(obj)
            return obj

    def delete(self, client_id: int) -> bool:
        """Удаляет клиента. Возвращает True, если удалён."""
        with get_session() as s:
            obj = s.get(ClientORM, client_id)
            if not obj:
                return False
            s.delete(obj); s.commit()
            return True


class HallRepository:
    """CRUD для залов."""

    def create(self, name: str, description: str, price_per_hour: Decimal) -> HallORM:
        with get_session() as s:
            obj = HallORM(name=name, description=description, price_per_hour=price_per_hour)
            s.add(obj); s.commit(); s.refresh(obj)
            return obj

    def list_all(self, only_active: bool = False) -> list[HallORM]:
        with get_session() as s:
            stmt = select(HallORM)
            if only_active:
                stmt = stmt.where(HallORM.is_active.is_(True))
            return list(s.scalars(stmt).all())

    def delete(self, hall_id: int) -> bool:
        with get_session() as s:
            obj = s.get(HallORM, hall_id)
            if not obj:
                return False
            s.delete(obj); s.commit()
            return True


class EquipmentRepository:
    """CRUD для оборудования."""

    def create(self, name: str, category: str, price_per_day: Decimal) -> EquipmentORM:
        with get_session() as s:
            obj = EquipmentORM(name=name, category=category, price_per_day=price_per_day)
            s.add(obj); s.commit(); s.refresh(obj)
            return obj

    def list_all(self) -> list[EquipmentORM]:
        with get_session() as s:
            return list(s.scalars(select(EquipmentORM)).all())

    def delete(self, equipment_id: int) -> bool:
        with get_session() as s:
            obj = s.get(EquipmentORM, equipment_id)
            if not obj:
                return False
            s.delete(obj); s.commit()
            return True


    def toggle_available(self, equipment_id: int) -> bool:
        """
        Переключает доступность оборудования на противоположную.

        Args:
            equipment_id: ID оборудования.

        Returns:
            True, если оборудование найдено и обновлено.
            False, если оборудования с таким ID нет.
        """
        with get_session() as s:
            obj = s.get(EquipmentORM, equipment_id)
            if not obj:
                return False
            obj.is_available = not obj.is_available
            s.commit()
            return True

class StatusRepository:
    """CRUD для статусов."""

    def list_all(self) -> list[StatusORM]:
        with get_session() as s:
            return list(s.scalars(select(StatusORM)).all())

    def create(self, name: str) -> StatusORM:
        with get_session() as s:
            obj = StatusORM(name=name)
            s.add(obj); s.commit(); s.refresh(obj)
            return obj


class UserRepository:
    """CRUD для пользователей."""

    def create(self, role_id: int, login: str, password_hash: str, full_name: str) -> UserORM:
        with get_session() as s:
            obj = UserORM(role_id=role_id, login=login,
                          password_hash=password_hash, full_name=full_name)
            s.add(obj); s.commit(); s.refresh(obj)
            return obj

    def get_by_login(self, login: str) -> UserORM | None:
        """Возвращает пользователя по логину, сразу подгружая роль."""
        from sqlalchemy.orm import joinedload

        with get_session() as s:
            return s.scalar(
                select(UserORM)
                .options(joinedload(UserORM.role))
                .where(UserORM.login == login)
            )

    def list_all(self) -> list[UserORM]:
        """Возвращает всех пользователей с подгрузкой роли."""
        from sqlalchemy.orm import joinedload

        with get_session() as s:
            stmt = select(UserORM).options(joinedload(UserORM.role))
            return list(s.scalars(stmt).unique().all())

    def delete(self, user_id: int) -> bool:
        with get_session() as s:
            obj = s.get(UserORM, user_id)
            if not obj:
                return False
            s.delete(obj); s.commit()
            return True

class TaskRepository:
    """CRUD для задач в блоке 'Ожидания решений'."""

    def list_all(self) -> list[TaskORM]:
        """Возвращает все задачи в порядке добавления."""
        with get_session() as s:
            return list(s.scalars(select(TaskORM).order_by(TaskORM.task_id)).all())

    def create(self, text: str) -> TaskORM:
        """Создаёт новую задачу."""
        with get_session() as s:
            obj = TaskORM(text=text)
            s.add(obj)
            s.commit()
            s.refresh(obj)
            return obj

    def delete(self, task_id: int) -> bool:
        """Удаляет задачу по ID."""
        with get_session() as s:
            obj = s.get(TaskORM, task_id)
            if not obj:
                return False
            s.delete(obj)
            s.commit()
            return True

class BookingRepository:
    """CRUD для броней + агрегация для отчётов."""

    def create(self, client_id, hall_id, user_id, start, end,
               status_id, total_price, equipment_ids=None) -> BookingORM:
        with get_session() as s:
            obj = BookingORM(
                client_id=client_id, hall_id=hall_id, user_id=user_id,
                start_datetime=start, end_datetime=end,
                status_id=status_id, total_price=total_price,
            )
            s.add(obj); s.flush()
            for eq_id in equipment_ids or []:
                s.add(BookingEquipmentORM(booking_id=obj.booking_id,
                                          equipment_id=eq_id, quantity=1))
            s.commit(); s.refresh(obj)
            return obj

    def update_status(self, booking_id: int, status_id: int) -> bool:
        """Меняет статус брони по ID. Возвращает True, если бронь найдена."""
        with get_session() as s:
            obj = s.get(BookingORM, booking_id)
            if not obj:
                return False
            obj.status_id = status_id
            s.commit()
            return True

    def list_all(self) -> list[BookingORM]:
        """Возвращает все брони с подгрузкой связанных объектов."""
        from sqlalchemy.orm import joinedload

        with get_session() as s:
            stmt = (
                select(BookingORM)
                .options(
                    joinedload(BookingORM.client),
                    joinedload(BookingORM.hall),
                    joinedload(BookingORM.status),
                )
                .order_by(BookingORM.start_datetime.desc())
            )
            return list(s.scalars(stmt).unique().all())

    def list_by_user(self, user_id: int) -> list[BookingORM]:
        """Возвращает только брони, созданные указанным пользователем."""
        from sqlalchemy.orm import joinedload

        with get_session() as s:
            stmt = (
                select(BookingORM)
                .options(
                    joinedload(BookingORM.client),
                    joinedload(BookingORM.hall),
                    joinedload(BookingORM.status),
                )
                .where(BookingORM.user_id == user_id)
                .order_by(BookingORM.start_datetime.desc())
            )
            return list(s.scalars(stmt).unique().all())

    def list_by_date(self, day: datetime) -> list[BookingORM]:
        """Возвращает брони за указанный день с подгрузкой связанных объектов."""
        from sqlalchemy.orm import joinedload

        start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start.replace(hour=23, minute=59, second=59)
        with get_session() as s:
            stmt = (
                select(BookingORM)
                .options(
                    joinedload(BookingORM.client),
                    joinedload(BookingORM.hall),
                    joinedload(BookingORM.status),
                )
                .where(
                    BookingORM.start_datetime >= start,
                    BookingORM.start_datetime <= end,
                )
            )
            return list(s.scalars(stmt).unique().all())

    def delete(self, booking_id: int) -> bool:
        with get_session() as s:
            obj = s.get(BookingORM, booking_id)
            if not obj:
                return False
            s.delete(obj); s.commit()
            return True

    def revenue_report(self) -> dict:
        """KPI + разбивка выручки по залам."""
        with get_session() as s:
            total = s.scalar(select(func.coalesce(func.sum(BookingORM.total_price), 0))) or 0
            count = s.scalar(select(func.count(BookingORM.booking_id))) or 0
            rows = s.execute(
                select(HallORM.name, func.coalesce(func.sum(BookingORM.total_price), 0))
                .join(BookingORM, BookingORM.hall_id == HallORM.hall_id)
                .group_by(HallORM.name)
            ).all()
            return {
                "total_revenue": Decimal(total),
                "bookings_count": int(count),
                "by_hall": [(name, Decimal(amount)) for name, amount in rows],
            }


# =====================================================================
# SEED — начальные данные
# =====================================================================

def seed_database():
    """Заполняет БД начальными ролями, статусами, залами и пользователями."""
    Base.metadata.create_all(engine)

    with get_session() as s:
        # Роли
        if not s.scalar(select(RoleORM)):
            s.add_all([
                RoleORM(name="Администратор", description="Полный доступ"),
                RoleORM(name="Клиент", description="Ограниченный доступ"),
            ])
            # Демо-задачи
        if not s.scalar(select(TaskORM)):
            s.add_all([
                TaskORM(text="Собрать статистику по брони и выручке"),
                TaskORM(text="Клиент не отвечает на уточнение по редакции"),
                TaskORM(text="Перегорел лампа в постоянном свете"),
                TaskORM(text="Не работает кондиционер в зале 'Лофт'"),
                TaskORM(text="Не хватает базовых расходников"),
            ])
            s.commit()
            s.commit()

        # Статусы
        if not s.scalar(select(StatusORM)):
            s.add_all([
                StatusORM(name="Новая"),
                StatusORM(name="Подтверждена"),
                StatusORM(name="Отменена"),
                StatusORM(name="Завершена"),
            ])
            s.commit()

        # Залы
        if not s.scalar(select(HallORM)):
            s.add_all([
                HallORM(name="Зал A", description="Большой зал, 100 м²",
                        price_per_hour=Decimal("1500.00")),
                HallORM(name="Зал B", description="Средний зал, 60 м²",
                        price_per_hour=Decimal("1000.00")),
                HallORM(name="Зал C", description="Малый зал, 30 м²",
                        price_per_hour=Decimal("700.00")),
            ])
            s.commit()

        # Оборудование
        if not s.scalar(select(EquipmentORM)):
            s.add_all([
                EquipmentORM(name="Проектор", category="Видео",
                             price_per_day=Decimal("500.00")),
                EquipmentORM(name="Микрофон", category="Звук",
                             price_per_day=Decimal("300.00")),
                EquipmentORM(name="Флипчарт", category="Прочее",
                             price_per_day=Decimal("150.00")),
            ])
            s.commit()

        # Пользователи
        if not s.scalar(select(UserORM)):
            admin_role = s.scalar(select(RoleORM).where(RoleORM.name == "Администратор"))
            client_role = s.scalar(select(RoleORM).where(RoleORM.name == "Клиент"))
            s.add_all([
                UserORM(role_id=admin_role.role_id, login="admin",
                        password_hash=hash_password("admin123"),
                        full_name="Администратор Системы"),
                UserORM(role_id=client_role.role_id, login="client",
                        password_hash=hash_password("client123"),
                        full_name="Иван Иванов"),
            ])
            s.commit()

        # Демо-клиент
        if not s.scalar(select(ClientORM)):
            s.add(ClientORM(name="ООО Ромашка", phone="+7-900-000-00-01",
                            email="info@romashka.ru", notes="VIP"))
            s.add(ClientORM(name="ИП Петров", phone="+7-900-000-00-02",
                            email="petrov@mail.ru"))
            s.commit()


# =====================================================================
# UI LAYER — PyQt5
# =====================================================================

APP_STYLE = """
QWidget { background-color:#EAF2F5; color:#2B2B2B;
          font-family:'Segoe UI'; font-size:10pt; }
QMainWindow { background-color:#EAF2F5; }
QPushButton { background-color:#6F8E9E; color:white; border:none;
              padding:8px 16px; border-radius:6px; }
QPushButton:hover { background-color:#5E7C8C; }
QPushButton#accent { background-color:#D4A373; }
QPushButton#accent:hover { background-color:#C09066; }
QPushButton#danger { background-color:#C97B7B; }
QLineEdit, QComboBox, QDateTimeEdit, QTextEdit {
    background-color:#FDF6E3; border:1px solid #C8D4DA;
    border-radius:6px; padding:6px;
}
QTableWidget { background-color:#FDF6E3; gridline-color:#C8D4DA;
               border:1px solid #C8D4DA; border-radius:6px; }
QHeaderView::section { background-color:#D9E4EA; padding:6px; border:none; }
QLabel#title { font-size:14pt; font-weight:bold; }
QLabel#subtitle { font-size:11pt; font-weight:bold; }
QFrame#card { background-color:#B7C9D3; border-radius:10px; }
QFrame#tile { background-color:#FDF6E3; border:1px solid #C8D4DA;
              border-radius:8px; }
"""


# ---------- Переиспользуемые компоненты ----------

def make_button(text: str, slot, accent: bool = False, danger: bool = False) -> QPushButton:
    """Создаёт стилизованную кнопку."""
    b = QPushButton(text)
    if accent:
        b.setObjectName("accent")
    elif danger:
        b.setObjectName("danger")
    b.clicked.connect(slot)
    return b


def make_table(headers: list[str]) -> QTableWidget:
    """Создаёт QTableWidget с заголовками, без вертикальных номеров строк."""
    t = QTableWidget()
    t.setColumnCount(len(headers))
    t.setHorizontalHeaderLabels(headers)
    # Растягиваем все столбцы, кроме последнего (Действия) — его ширина фиксирована
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    t.horizontalHeader().setSectionResizeMode(
        len(headers) - 1, QHeaderView.ResizeToContents
    )
    t.horizontalHeader().setMinimumSectionSize(160)
    t.setSelectionBehavior(QTableWidget.SelectRows)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(38)
    return t


# ---------- Экран авторизации ----------

class LoginView(QWidget):
    """Форма входа (Figma: 'Авторизация')."""

    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignCenter)

        header = QLabel("FS.Booking")
        header.setObjectName("title")
        header.setAlignment(Qt.AlignCenter)

        card = QFrame(); card.setObjectName("card"); card.setFixedWidth(340)
        cl = QVBoxLayout(card); cl.setContentsMargins(24, 24, 24, 24); cl.setSpacing(12)

        title = QLabel("Вход в аккаунт"); title.setAlignment(Qt.AlignCenter)
        title.setObjectName("subtitle")

        self.login_input = QLineEdit(); self.login_input.setPlaceholderText("Логин")
        self.password_input = QLineEdit(); self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.Password)

        btn_login = make_button("Войти", self._on_login, accent=True)
        btn_reg = make_button("Регистрация", main.show_register)
        btn_forgot = make_button("Забыли пароль?", main.show_forgot)

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
        """Обработчик входа."""
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


# ---------- Экран регистрации ----------

class RegisterView(QWidget):
    """Форма регистрации (Figma: 'Регистрация')."""

    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        root = QVBoxLayout(self); root.setAlignment(Qt.AlignCenter)

        header = QLabel("FS.Booking"); header.setObjectName("title")
        header.setAlignment(Qt.AlignCenter)

        card = QFrame(); card.setObjectName("card"); card.setFixedWidth(340)
        cl = QVBoxLayout(card); cl.setContentsMargins(24, 24, 24, 24); cl.setSpacing(10)

        title = QLabel("Регистрация"); title.setAlignment(Qt.AlignCenter)
        title.setObjectName("subtitle")

        self.full_name = QLineEdit(); self.full_name.setPlaceholderText("ФИО")
        self.login = QLineEdit(); self.login.setPlaceholderText("Логин")
        self.password = QLineEdit(); self.password.setPlaceholderText("Пароль")
        self.password.setEchoMode(QLineEdit.Password)
        self.password2 = QLineEdit(); self.password2.setPlaceholderText("Повтор пароля")
        self.password2.setEchoMode(QLineEdit.Password)

        btn_submit = make_button("Зарегистрироваться", self._on_submit, accent=True)
        btn_back = make_button("Назад", main.show_login)

        for w in (title, self.full_name, self.login, self.password,
                  self.password2, btn_submit, btn_back):
            cl.addWidget(w)

        root.addWidget(header); root.addSpacing(16)
        root.addWidget(card, alignment=Qt.AlignCenter)

    def _on_submit(self):
        if not all([self.full_name.text().strip(), self.login.text().strip(),
                    self.password.text(), self.password2.text()]):
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
            self.main.show_error(str(e)); return

        with get_session() as s:
            role = s.scalar(select(RoleORM).where(RoleORM.name == "Клиент"))
            role_id = role.role_id if role else 1
        self.main.user_repo.create(role_id, self.login.text().strip(),
                                   pwd_hash, self.full_name.text().strip())
        self.main.show_info("Регистрация успешна. Войдите в систему.")
        self.main.show_login()


# ---------- Экран восстановления пароля ----------

class ForgotView(QWidget):
    """Форма восстановления пароля (Figma: 'Забыли пароль')."""

    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        root = QVBoxLayout(self); root.setAlignment(Qt.AlignCenter)

        header = QLabel("FS.Booking"); header.setObjectName("title")
        header.setAlignment(Qt.AlignCenter)

        card = QFrame(); card.setObjectName("card"); card.setFixedWidth(340)
        cl = QVBoxLayout(card); cl.setContentsMargins(24, 24, 24, 24); cl.setSpacing(10)

        title = QLabel("Восстановление пароля"); title.setAlignment(Qt.AlignCenter)
        title.setObjectName("subtitle")

        self.login_input = QLineEdit(); self.login_input.setPlaceholderText("Логин или e-mail")

        btn_send = make_button("Отправить", self._on_send, accent=True)
        btn_back = make_button("Назад", main.show_login)

        for w in (title, self.login_input, btn_send, btn_back):
            cl.addWidget(w)

        root.addWidget(header); root.addSpacing(16)
        root.addWidget(card, alignment=Qt.AlignCenter)

    def _on_send(self):
        self.main.show_info("Ссылка для восстановления отправлена (демо).")
        self.main.show_login()


# ---------- Боковая панель навигации ----------

def build_sidebar(main: "MainWindow", items: list[tuple[str, callable]]) -> QFrame:
    """Строит боковую панель с кнопками навигации."""
    side = QFrame()
    side.setFixedWidth(180)
    side.setStyleSheet("background-color:#FDF6E3; border-right:1px solid #C8D4DA;")
    layout = QVBoxLayout(side)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(6)

    logo = QLabel("FS.Booking")
    logo.setObjectName("subtitle")
    layout.addWidget(logo)
    layout.addSpacing(10)

    sidebar_button_style = """
        QPushButton {
            background-color: #D9E4EA;
            color: #2B2B2B;
            text-align: left;
            padding: 8px 12px;
            border: 1px solid #C8D4DA;
            border-radius: 6px;
            font-size: 10pt;
        }
        QPushButton:hover {
            background-color: #B7C9D3;
            color: #1A1A1A;
        }def build_header
        QPushButton:pressed {
            background-color: #A5B8C2;
        }
    """

    for text, slot in items:
        btn = make_button(text, slot)
        btn.setStyleSheet(sidebar_button_style)
        layout.addWidget(btn)

    layout.addStretch()
    logout_btn = make_button("Выйти", main.logout, danger=True)
    logout_btn.setStyleSheet(sidebar_button_style)
    layout.addWidget(logout_btn)
    return side


def build_header(text: str) -> QLabel:
    """Строит заголовок экрана."""
    lbl = QLabel(text)
    lbl.setObjectName("title")
    return lbl


def build_topbar(main: "MainWindow", title: str) -> QHBoxLayout:
    """Строит верхнюю панель с кнопкой 'Назад' и заголовком экрана."""
    bar = QHBoxLayout()
    back_btn = QPushButton("← Назад в меню")
    back_btn.setObjectName("accent")
    back_btn.setFixedWidth(160)
    back_btn.clicked.connect(main.show_dashboard)
    bar.addWidget(back_btn)
    bar.addSpacing(10)
    bar.addWidget(build_header(title))
    bar.addStretch()
    return bar

# ---------- Экран профиля клиента ----------

class ClientProfileView(QWidget):
    """Профиль клиента (Figma: 'Мой профиль (клиент)')."""

    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        self._build()

    def _build(self):
        """Собирает интерфейс: боковое меню, личные данные, таблица своих броней."""
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

        # Карточка с личными данными
        info_card = QFrame()
        info_card.setObjectName("card")
        info_card.setStyleSheet(
            "QFrame#card { background-color:#FDF6E3; border:1px solid #C8D4DA; "
            "border-radius:8px; padding:12px; }"
        )
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(16, 12, 16, 12)
        info_layout.setSpacing(6)

        self.info_label = QLabel()
        self.info_label.setStyleSheet("color:#2B2B2B; font-size:11pt;")
        info_layout.addWidget(self.info_label)
        body.addWidget(info_card)

        # Кнопка создания брони
        btn_new = make_button("+ Создать бронь", self._on_create_booking, accent=True)
        body.addWidget(btn_new, alignment=Qt.AlignLeft)

        # Заголовок для таблицы
        body.addWidget(QLabel("Мои брони:"))

        # Таблица своих броней
        self.table = make_table(
            ["ID", "Зал", "Начало", "Окончание", "Статус", "Сумма"]
        )
        body.addWidget(self.table)

        body.addWidget(
            make_button("Обновить", self.refresh),
            alignment=Qt.AlignLeft,
        )

        container = QWidget()
        container.setLayout(body)
        root.addWidget(container, stretch=1)

    def refresh(self):
        """Обновляет личные данные и список своих броней."""
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

    def _on_create_booking(self):
        """Открывает диалог создания брони от имени текущего клиента."""
        dlg = BookingDialog(self.main)
        if dlg.exec_() == QDialog.Accepted:
            self.refresh()

    def showEvent(self, event):
        """При показе экрана — обновляет данные."""
        self.refresh()
        super().showEvent(event)

# ---------- Экран профиля администратора ----------

class AdminProfileView(QWidget):
    """Профиль администратора (Figma: 'Мой профиль (администратор)')."""

    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        self.period = "month"       # month / quarter / year
        self.sel_year = datetime.now().year
        self.sel_month = datetime.now().month
        self.sel_quarter = ((datetime.now().month - 1) // 3) + 1
        self._build()
    def _build(self):
        """Собирает интерфейс панели администратора по макету Figma."""
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
        client_card = QFrame()
        client_card.setStyleSheet(
            "background-color:#DCE9EF; border:1px solid #B7C9D3; "
            "border-radius:8px; padding:8px;"
        )
        cc_layout = QHBoxLayout(client_card)
        cc_layout.setContentsMargins(12, 8, 12, 8)
        cc_layout.setSpacing(12)

        info = QVBoxLayout()
        info.setSpacing(2)
        self.client_name = QLabel("—")
        self.client_name.setStyleSheet("font-size:11pt; font-weight:bold; color:#2B2B2B;")
        self.client_phone = QLabel("+7 991 114 82 34")
        self.client_phone.setStyleSheet("color:#2B2B2B; font-size:9pt;")
        info.addWidget(self.client_name)
        info.addWidget(self.client_phone)
        cc_layout.addLayout(info)
        cc_layout.addStretch()

        # Ограничиваем высоту карточки
        client_card.setMaximumHeight(110)
        body.addWidget(client_card)

        # ---------- Фильтр периода ----------
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("Период:"))

        self.period_buttons = {}
        for key in ("month", "quarter", "year"):
            btn = QPushButton("")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, k=key: self._on_period_click(k))
            self.period_buttons[key] = btn
            filter_row.addWidget(btn)

        self.period_buttons["month"].setChecked(True)
        filter_row.addStretch()
        body.addLayout(filter_row)
        self._update_period_styles()

        # ---------- Основная зона ----------
        main_row = QHBoxLayout()
        main_row.setSpacing(14)

        # --- Левая колонка ---
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        # Карточка выручки
        revenue_card = QFrame()
        revenue_card.setStyleSheet(
            "background-color:#FDF6E3; border:1px solid #C8D4DA; border-radius:10px; padding:12px;"
        )
        rc_layout = QVBoxLayout(revenue_card)
        rc_layout.setContentsMargins(16, 12, 16, 12)
        rc_layout.setSpacing(6)
        rc_layout.addWidget(QLabel("Выручка за период"))
        self.revenue_value = QLabel("0 ₽")
        self.revenue_value.setStyleSheet(
            "font-size:22pt; font-weight:bold; color:#2B2B2B;"
        )
        rc_layout.addWidget(self.revenue_value)
        left_col.addWidget(revenue_card)


        left_col.addStretch()
        main_row.addLayout(left_col, stretch=2)

        # --- Правая колонка — «Ожидания решений» ---
        tasks_card = QFrame()
        tasks_card.setStyleSheet(
            "background-color:#FDF6E3; border:1px solid #C8D4DA; border-radius:10px; padding:12px;"
        )
        tc_layout = QVBoxLayout(tasks_card)
        tc_layout.setContentsMargins(16, 12, 16, 12)
        tc_layout.setSpacing(8)

        tasks_title = QLabel("Ожидания решений")
        tasks_title.setStyleSheet("font-size:12pt; font-weight:bold; color:#2B2B2B;")
        tc_layout.addWidget(tasks_title)

        # Кнопка добавления
        add_btn = QPushButton("+ Добавить задачу")
        add_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #6F8E9E;"
            "  color: #FFFFFF;"
            "  border: none;"
            "  border-radius: 8px;"
            "  padding: 8px 16px;"
            "  font-weight: bold;"
            "  font-size: 10pt;"
            "}"
            "QPushButton:hover { background-color: #5E7C8C; }"
            "QPushButton:pressed { background-color: #4F6A78; }"
        )
        add_btn.clicked.connect(self._on_add_task)
        tc_layout.addWidget(add_btn)

        # Контейнер для списка задач (динамически наполняется)
        self.tasks_container = QVBoxLayout()
        self.tasks_container.setSpacing(6)
        tc_layout.addLayout(self.tasks_container)

        tc_layout.addStretch()
        tasks_card.setMinimumWidth(320)
        main_row.addWidget(tasks_card, stretch=1)
        body.addLayout(main_row)
        body.addStretch()

        container = QWidget()
        container.setLayout(body)
        root.addWidget(container, stretch=1)

    # ---------- Работа с периодом ----------

    def _on_period_click(self, key: str):
        """Обрабатывает клик по кнопке периода: открывает диалог выбора даты."""
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

    def _select_month(self) -> bool:
        """Диалог выбора месяца и года. Возвращает True, если пользователь подтвердил."""
        months = [
            "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
            "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
        ]
        years = [str(y) for y in range(datetime.now().year - 3, datetime.now().year + 2)]

        dlg = QDialog(self)
        dlg.setWindowTitle("Выбор месяца")
        dlg.setMinimumWidth(260)
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

    def _select_quarter(self) -> bool:
        """Диалог выбора квартала и года."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Выбор квартала")
        dlg.setMinimumWidth(260)
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

    def _select_year(self) -> bool:
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
        """Меняет текст и стиль кнопок периода: активная — тёмная."""
        labels = {
            "month": self._month_label(),
            "quarter": self._quarter_label(),
            "year": str(self.sel_year),
        }

        for key, btn in self.period_buttons.items():
            btn.setText(labels[key])
            if key == self.period:
                btn.setStyleSheet(
                    "QPushButton { background-color:#6F8E9E; color:white; "
                    "border:1px solid #5E7C8C; border-radius:14px; padding:4px 14px; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background-color:#FDF6E3; color:#2B2B2B; "
                    "border:1px solid #C8D4DA; border-radius:14px; padding:4px 14px; }"
                    "QPushButton:hover { background-color:#E8D9B8; }"
                )

    def _month_label(self) -> str:
        """Возвращает название выбранного месяца и года в формате 'Сент.2026'."""
        months_short = [
            "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
            "Июл", "Авг", "Сент", "Окт", "Ноя", "Дек",
        ]
        return f"{months_short[self.sel_month - 1]}.{self.sel_year}"

    def _quarter_label(self) -> str:
        """Возвращает название выбранного квартала и года в формате 'III кв. 2026'."""
        roman = ["I", "II", "III", "IV"]
        return f"{roman[self.sel_quarter - 1]} кв. {self.sel_year}"

    def _period_range(self):
        """Возвращает (start, end) — границы выбранного периода."""
        if self.period == "month":
            start = datetime(self.sel_year, self.sel_month, 1, 0, 0, 0)
            # Конец месяца
            if self.sel_month == 12:
                end = datetime(self.sel_year, 12, 31, 23, 59, 59)
            else:
                end = datetime(self.sel_year, self.sel_month + 1, 1, 0, 0, 0)
                end = end.replace(hour=0) - timedelta(seconds=1)
        elif self.period == "quarter":
            q_month = (self.sel_quarter - 1) * 3 + 1
            start = datetime(self.sel_year, q_month, 1, 0, 0, 0)
            end_month = q_month + 2
            # Конец последнего месяца квартала
            if end_month == 12:
                end = datetime(self.sel_year, 12, 31, 23, 59, 59)
            else:
                end = datetime(self.sel_year, end_month + 1, 1, 0, 0, 0)
                end = end - timedelta(seconds=1)
        else:  # year
            start = datetime(self.sel_year, 1, 1, 0, 0, 0)
            end = datetime(self.sel_year, 12, 31, 23, 59, 59)
        return start, end

    # ---------- Работа с задачами ----------

    def _reload_tasks(self):
        """Перерисовывает список задач из БД."""
        # Очистить контейнер
        while self.tasks_container.count():
            item = self.tasks_container.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        tasks = self.main.task_repo.list_all()
        for task in tasks:
            self.tasks_container.addWidget(self._make_task_row(task.task_id, task.text))

    def _make_task_row(self, task_id: int, text: str) -> QFrame:
        """Одна строка задачи с кнопкой удаления."""
        row = QFrame()
        row.setStyleSheet(
            "background-color:#FFFFFF; border:1px solid #C8D4DA; "
            "border-radius:8px; padding:6px;"
        )
        h = QHBoxLayout(row)
        h.setContentsMargins(12, 8, 12, 8)
        h.setSpacing(10)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setMinimumHeight(44)
        label.setMinimumWidth(180)
        label.setStyleSheet(
            "color:#2B2B2B; font-size:10pt; padding: 4px;"
        )
        h.addWidget(label, stretch=1)

        del_btn = QPushButton("×")
        del_btn.setFixedSize(24, 24)
        del_btn.setStyleSheet(
            "QPushButton { background-color:#C97B7B; color:white; border:none; "
            "border-radius:12px; font-weight:bold; } "
            "QPushButton:hover { background-color:#A85F5F; }"
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

    def _on_delete_task(self, task_id: int):
        """Удаляет задачу без подтверждения."""
        if self.main.task_repo.delete(task_id):
            self._reload_tasks()

    # ---------- Обновление данных ----------

    def refresh(self):
        """Обновляет данные панели администратора (профиль, выручка, часы)."""
        user = self.main.current_user
        if user:
            self.client_name.setText(user.full_name or "—")

        start, end = self._period_range()

         #Выручка за период

        with get_session() as s:
            total = s.scalar(
                select(func.coalesce(func.sum(BookingORM.total_price), 0)).where(
                    BookingORM.start_datetime >= start,
                    BookingORM.start_datetime <= end,
            )
            ) or 0
        self.revenue_value.setText(f"{Decimal(total):.2f} ₽")
        # Обновить задачи
        self._reload_tasks()

    def showEvent(self, event):
        """При показе — обновить данные."""
        self.refresh()
        super().showEvent(event)

# ---------- Экран календаря ----------

class CalendarView(QWidget):
    """Календарь броней (Figma: 'Дашборд/Календарь')."""

    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(20, 20, 20, 20); root.setSpacing(10)
        root.addLayout(build_topbar(self.main, "Календарь броней"))

        top = QHBoxLayout()
        top.addWidget(QLabel("Дата:"))
        self.date_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.setMinimumWidth(160)
        self.date_edit.setCalendarPopup(True)
        top.addWidget(self.date_edit)
        top.addWidget(make_button("Показать", self.refresh, accent=True))
        top.addStretch()
        root.addLayout(top)

        self.table = make_table(["Зал", "Начало", "Окончание", "Клиент", "Статус"])
        root.addWidget(self.table)

    def refresh(self):
        day = self.date_edit.dateTime().toPyDateTime()
        bookings = self.main.booking_repo.list_by_date(day)
        self.table.setRowCount(len(bookings))
        for i, b in enumerate(bookings):
            values = [
                b.hall.name if b.hall else "—",
                b.start_datetime.strftime("%H:%M"),
                b.end_datetime.strftime("%H:%M"),
                b.client.name if b.client else "—",
                b.status.name if b.status else "—",
            ]
            for j, v in enumerate(values):
                self.table.setItem(i, j, QTableWidgetItem(v))

    def showEvent(self, event):
        self.refresh(); super().showEvent(event)


# ---------- Экран броней ----------

class BookingDialog(QDialog):
    """Диалог создания брони."""

    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        self.setWindowTitle("Новая бронь")
        self.setMinimumWidth(420)

        form = QFormLayout(self)

        self.client_input = QLineEdit()
        self.client_input.setPlaceholderText("Введите имя клиента")

        self.hall_combo = QComboBox()
        for h in main.hall_repo.list_all(only_active=True):
            self.hall_combo.addItem(f"{h.name} ({h.price_per_hour} ₽/ч)",
                                    h.hall_id)

        self.start_edit = QDateTimeEdit(QDateTime.currentDateTime())
        self.start_edit.setDisplayFormat("dd.MM.yyyy HH:mm")
        self.end_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self.end_edit.setDisplayFormat("dd.MM.yyyy HH:mm")

        self.equip_combo = QComboBox()
        self.equip_combo.addItem("— без оборудования —", None)
        for e in main.equipment_repo.list_all():
            if e.is_available:
                self.equip_combo.addItem(f"{e.name} ({e.price_per_day} ₽)", e.equipment_id)

        form.addRow("Клиент:", self.client_input)
        form.addRow("Зал:", self.hall_combo)
        form.addRow("Начало:", self.start_edit)
        form.addRow("Окончание:", self.end_edit)
        form.addRow("Оборудование:", self.equip_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_save(self):
        try:
            client_name = self.client_input.text().strip()
            if not client_name:
                self.main.show_error("Введите имя клиента.")
                return

            # Ищем клиента по имени (регистронезависимо)
            all_clients = self.main.client_repo.list_all()
            needle = client_name.lower()
            existing = next(
                (c for c in all_clients if (c.name or "").lower() == needle),
                None,
            )

            if existing is not None:
                client_id = existing.client_id
            else:
                # Создаём нового клиента с пустыми контактами
                new_client = self.main.client_repo.create(
                    name=client_name,
                    phone="",
                    email="",
                    notes="",
                )
                client_id = new_client.client_id
            hall_id = self.hall_combo.currentData()
            start = self.start_edit.dateTime().toPyDateTime()
            end = self.end_edit.dateTime().toPyDateTime()

            with get_session() as s:
                hall = s.get(HallORM, hall_id)
            price = Decimal(hall.price_per_hour)

            eq_id = self.equip_combo.currentData()
            eq_prices = []
            if eq_id is not None:
                with get_session() as s:
                    eq = s.get(EquipmentORM, eq_id)
                eq_prices.append(Decimal(eq.price_per_day))

            total = calculate_booking_price(start, end, price, eq_prices)

            with get_session() as s:
                status = s.scalar(select(StatusORM).where(StatusORM.name == "Новая"))
                status_id = status.status_id if status else 1

            self.main.booking_repo.create(
                client_id=client_id, hall_id=hall_id,
                user_id=self.main.current_user.user_id,
                start=start, end=end, status_id=status_id,
                total_price=total,
                equipment_ids=[eq_id] if eq_id else [],
            )
            self.main.show_info(f"Бронь создана. Стоимость: {total} ₽")
            self.accept()
        except InvalidBookingPeriodError as e:
            self.main.show_error(str(e))
        except Exception as e:  # noqa: BLE001
            self.main.show_error(f"Ошибка: {e}")


class BookingView(QWidget):
    """Список броней + создание/удаление (Figma: 'Брони')."""

    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(20, 20, 20, 20); root.setSpacing(10)
        root.addLayout(build_topbar(self.main, "Брони"))

        actions = QHBoxLayout()
        actions.addWidget(make_button("+ Создать", self._on_create, accent=True))
        if self.main.current_user and self.main.current_user.role:
            role_name = self.main.current_user.role.name.lower()
            if "админ" in role_name or "admin" in role_name:
                actions.addWidget(make_button("Сменить статус", self._on_change_status))
                actions.addWidget(
                    make_button("Удалить выбранную", self._on_delete, danger=True)
                )
        actions.addWidget(make_button("Обновить", self.refresh))
        actions.addStretch()
        root.addLayout(actions)

        self.table = make_table(
            ["ID", "Клиент", "Зал", "Начало", "Окончание", "Статус", "Сумма"]
        )
        root.addWidget(self.table)

    def refresh(self):
        """Обновляет список броней — все для админа, только свои для клиента."""
        user = self.main.current_user
        is_admin = user and user.role and "админ" in user.role.name.lower()

        if is_admin:
            bookings = self.main.booking_repo.list_all()
        else:
            bookings = self.main.booking_repo.list_by_user(user.user_id)

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

    def _on_create(self):
        dlg = BookingDialog(self.main)
        if dlg.exec_() == QDialog.Accepted:
            self.refresh()

    def _on_change_status(self):
        """Открывает диалог смены статуса выбранной брони."""
        row = self.table.currentRow()
        if row < 0:
            self.main.show_error("Выберите бронь.")
            return
        booking_id = int(self.table.item(row, 0).text())

        statuses = self.main.status_repo.list_all()
        if not statuses:
            self.main.show_error("Нет доступных статусов в справочнике.")
            return

        # Диалог с выпадающим списком
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Смена статуса брони #{booking_id}")
        dlg.setMinimumWidth(300)
        form = QFormLayout(dlg)

        combo = QComboBox()
        for st in statuses:
            combo.addItem(st.name, st.status_id)
        form.addRow("Новый статус:", combo)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)

        if dlg.exec_() == QDialog.Accepted:
            new_status_id = combo.currentData()
            if self.main.booking_repo.update_status(booking_id, new_status_id):
                self.main.show_info("Статус изменён.")
                self.refresh()
            else:
                self.main.show_error("Бронь не найдена.")

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
        self.refresh(); super().showEvent(event)


# ---------- Экран клиентов ----------

class ClientsView(QWidget):
    """CRUD клиентов (Figma: 'Клиенты')."""

    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(20, 20, 20, 20); root.setSpacing(10)
        root.addLayout(build_topbar(self.main, "Клиенты"))

        top = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Поиск по имени...")
        top.addWidget(self.search)
        top.addWidget(make_button("Найти", self.refresh, accent=True))
        top.addWidget(make_button("+ Добавить", self._on_add))
        top.addWidget(make_button("Удалить", self._on_delete, danger=True))
        root.addLayout(top)

        self.table = make_table(["ID", "Имя", "Телефон", "Email", "Заметки"])
        root.addWidget(self.table)

    def refresh(self):
        clients = self.main.client_repo.list_all(search=self.search.text().strip())
        self.table.setRowCount(len(clients))
        for i, c in enumerate(clients):
            for j, v in enumerate([str(c.client_id), c.name, c.phone, c.email, c.notes or ""]):
                self.table.setItem(i, j, QTableWidgetItem(v))
    def _on_add(self):
        dlg = QDialog(self); dlg.setWindowTitle("Новый клиент")
        form = QFormLayout(dlg)
        name = QLineEdit(); phone = QLineEdit(); email = QLineEdit(); notes = QLineEdit()
        form.addRow("Имя:", name)
        form.addRow("Телефон:", phone)
        form.addRow("Email:", email)
        form.addRow("Заметки:", notes)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec_() == QDialog.Accepted and name.text().strip():
            try:
                phone_normalized = normalize_phone(phone.text())
            except ValidationError as e:
                self.main.show_error(str(e))
                return
            self.main.client_repo.create(name.text().strip(), phone_normalized,
                                         email.text(), notes.text())
            self.refresh()

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            self.main.show_error("Выберите клиента."); return
        client_id = int(self.table.item(row, 0).text())
        if self.main.client_repo.delete(client_id):
            self.main.show_info("Клиент удалён."); self.refresh()

    def showEvent(self, event):
        self.refresh(); super().showEvent(event)


# ---------- Экран отчётов ----------

class ReportsView(QWidget):
    """Отчёты (Figma: 'Отчёты')."""

    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(20, 20, 20, 20); root.setSpacing(10)
        root.addLayout(build_topbar(self.main, "Отчёты"))

        self.kpi = QLabel(); self.kpi.setObjectName("subtitle")
        root.addWidget(self.kpi)

        root.addWidget(QLabel("Выручка по залам:"))
        self.table = make_table(["Зал", "Выручка"])
        root.addWidget(self.table)

        root.addWidget(make_button("Обновить", self.refresh, accent=True),
                       alignment=Qt.AlignLeft)
        root.addWidget(make_button("Сохранить в PDF", self._export_pdf),
                       alignment=Qt.AlignLeft)

    def refresh(self):
        r = self.main.booking_repo.revenue_report()
        self.kpi.setText(
            f"Выручка: <b>{r['total_revenue']} ₽</b> | Броней: <b>{r['bookings_count']}</b>"
        )
        self.table.setRowCount(len(r["by_hall"]))
        for i, (name, amount) in enumerate(r["by_hall"]):
            self.table.setItem(i, 0, QTableWidgetItem(name))
            self.table.setItem(i, 1, QTableWidgetItem(f"{amount} ₽"))

    def _export_pdf(self):
        """Экспортирует отчёт (KPI + выручка по залам) в PDF-файл."""
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from datetime import datetime as _dt
        from PyQt5.QtWidgets import QFileDialog

        # Спросить у пользователя, куда сохранить
        default_name = f"report_{_dt.now().strftime('%Y%m%d_%H%M')}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить отчёт", default_name, "PDF (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        # Зарегистрировать шрифт с поддержкой кириллицы
        # (встроенный Helvetica не умеет русские буквы)
        font_name = "Helvetica"
        try:
            import os
            # Ищем DejaVuSans в системе Windows
            for candidate in (
                "C:/Windows/Fonts/DejaVuSans.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/times.ttf",
            ):
                if os.path.exists(candidate):
                    pdfmetrics.registerFont(TTFont("CustomFont", candidate))
                    font_name = "CustomFont"
                    break
        except Exception:  # noqa: BLE001
            pass

        # Собрать данные
        r = self.main.booking_repo.revenue_report()

        # Создать PDF
        c = canvas.Canvas(path, pagesize=A4)
        width, height = A4
        y = height - 60

        c.setFont(font_name, 18)
        c.drawString(50, y, "FS.Booking — Отчёт")
        y -= 30

        c.setFont(font_name, 10)
        c.drawString(50, y, f"Дата формирования: {_dt.now().strftime('%d.%m.%Y %H:%M')}")
        y -= 30

        c.setFont(font_name, 13)
        c.drawString(50, y, "Ключевые показатели:")
        y -= 22

        c.setFont(font_name, 11)
        c.drawString(70, y, f"Общая выручка: {r['total_revenue']} руб.")
        y -= 18
        c.drawString(70, y, f"Количество броней: {r['bookings_count']}")
        y -= 30

        c.setFont(font_name, 13)
        c.drawString(50, y, "Выручка по залам:")
        y -= 22

        c.setFont(font_name, 11)
        c.drawString(70, y, "Зал")
        c.drawString(300, y, "Выручка")
        y -= 6
        c.line(70, y, 480, y)
        y -= 16

        for name, amount in r["by_hall"]:
            c.drawString(70, y, str(name))
            c.drawString(300, y, f"{amount} руб.")
            y -= 18
            if y < 60:
                c.showPage()
                c.setFont(font_name, 11)
                y = height - 60

        c.setFont(font_name, 9)
        c.drawString(50, 40, "Документ сгенерирован автоматически в FS.Booking")
        c.save()

        self.main.show_info(f"Отчёт сохранён: {path}")
    def showEvent(self, event):
        self.refresh(); super().showEvent(event)


# ---------- Универсальный экран-справочник ----------

class ReferenceView(QWidget):
    """Универсальный CRUD-экран для справочников."""

    def __init__(self, main: "MainWindow", title: str,
                 headers: list[str], loader, on_add=None, on_delete=None, on_toggle=None):
        super().__init__()
        self.main = main
        self.loader = loader
        self.on_add = on_add
        self.on_delete = on_delete
        self.on_toggle = on_toggle

        root = QVBoxLayout(self); root.setContentsMargins(20, 20, 20, 20); root.setSpacing(10)
        root.addLayout(build_topbar(main, title))

        actions = QHBoxLayout()
        if on_add:
            actions.addWidget(make_button("+ Добавить", self._on_add_click, accent=True))
        if on_delete:
            actions.addWidget(make_button("Удалить", self._on_delete_click, danger=True))
        if self.on_toggle is not None:
            actions.addWidget(make_button("Переключить доступность", self._on_toggle_click))
        actions.addWidget(make_button("Обновить", self.refresh))
        actions.addStretch()
        root.addLayout(actions)

        self.table = make_table(headers)
        root.addWidget(self.table)

    def refresh(self):
        rows = self.loader()
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, v in enumerate(row):
                self.table.setItem(i, j, QTableWidgetItem(str(v)))

    def _on_add_click(self):
        if self.on_add:
            self.on_add(self)
            self.refresh()

    def _on_delete_click(self):
        row = self.table.currentRow()
        if row < 0:
            self.main.show_error("Выберите запись."); return
        obj_id = int(self.table.item(row, 0).text())
        if self.on_delete and self.on_delete(obj_id):
            self.main.show_info("Удалено."); self.refresh()

    def _on_toggle_click(self):
        """Переключает доступность выбранной записи (только для оборудования)."""
        row = self.table.currentRow()
        if row < 0:
            self.main.show_error("Выберите запись.")
            return
        obj_id = int(self.table.item(row, 0).text())
        if self.on_toggle is not None:
            if self.on_toggle(obj_id):
                self.main.show_info("Доступность изменена.")
                self.refresh()
            else:
                self.main.show_error("Запись не найдена.")

    def showEvent(self, event):
        self.refresh(); super().showEvent(event)


# ---------- Специализированные справочники ----------





# =====================================================================
# MAIN WINDOW
# =====================================================================

class ReferencesHubView(QWidget):
    """Объединённый справочник с вкладками: Залы, Оборудование, Статус, Пользователи."""

    def __init__(self, main: "MainWindow"):
        super().__init__()
        self.main = main
        self._build()

    def _build(self):
        """Строит экран: боковое меню + вкладки + таблицы."""
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

        # ----- Строка вкладок -----
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

        # Кнопка «+ Добавить …» — текст зависит от вкладки
        self.add_btn = QPushButton("+ Добавить")
        self.add_btn.setStyleSheet(
            "QPushButton { background-color:#FDF6E3; color:#2B2B2B; "
            "border:1px solid #C8D4DA; border-radius:14px; padding:6px 14px; }"
            "QPushButton:hover { background-color:#E8D9B8; }"
        )
        self.add_btn.clicked.connect(self._on_add_click)
        tabs_row.addWidget(self.add_btn)

        body.addLayout(tabs_row)

        # ----- Стек для страниц вкладок -----
        self.stack = QStackedWidget()
        body.addWidget(self.stack, stretch=1)

        # Каждая вкладка — QWidget с одной таблицей
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

        self.current_tab = "halls"
        self._switch_tab("halls")

    # ------- Создание страниц -------

    def _make_halls_page(self) -> QWidget:
        """Страница 'Залы'."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.halls_table = make_table(
            ["ID", "Название", "Описание", "Цена/час", "Статус", "Действия"]
        )
        layout.addWidget(self.halls_table)
        return page

    def _make_equipment_page(self) -> QWidget:
        """Страница 'Оборудование'."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.equipment_table = make_table(
            ["ID", "Название", "Категория", "Цена/день", "Доступно", "Действия"]
        )
        layout.addWidget(self.equipment_table)
        return page

    def _make_statuses_page(self) -> QWidget:
        """Страница 'Статус' — брони со статусами."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.statuses_table = make_table(
            ["ID", "Название объекта", "Тип", "Тек. статус", "Дата посл. изменения", "Действия"]
        )
        layout.addWidget(self.statuses_table)
        return page

    def _make_users_page(self) -> QWidget:
        """Страница 'Пользователи'."""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        self.users_table = make_table(
            ["ID", "ФИО", "Email", "Роль", "Статус", "Дата рег.", "Действия"]
        )
        layout.addWidget(self.users_table)
        return page

    # ------- Переключение вкладок -------

    def _switch_tab(self, key: str):
        """Переключает активную вкладку и обновляет кнопки и данные."""
        self.current_tab = key
        self.stack.setCurrentWidget(self.pages[key])

        labels = {
            "halls": "+ Добавить зал",
            "equipment": "+ Добавить оборудование",
            "statuses": "+ Добавить статус",
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
                    "QPushButton:hover { background-color:#E8D9B8; }"
                )


        self._refresh_current_tab()



    # ------- Обновление данных таблиц -------

    def _refresh_current_tab(self):
        """Обновляет таблицу активной вкладки."""
        if self.current_tab == "halls":
            self._refresh_halls()
        elif self.current_tab == "equipment":
            self._refresh_equipment()
        elif self.current_tab == "statuses":
            self._refresh_statuses()
        elif self.current_tab == "users":
            self._refresh_users()

    def _refresh_halls(self):
        """Заполняет таблицу 'Залы'."""
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

            # Кнопка удаления
                actions = self._make_action_buttons(
                h.hall_id,
                on_edit=self._edit_hall,
                on_delete=self._delete_hall,
            )
            self.halls_table.setCellWidget(i, 5, actions)

    def _refresh_equipment(self):
        """Заполняет таблицу 'Оборудование'."""
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

                actions = self._make_action_buttons(
                e.equipment_id,
                on_edit=self._edit_equipment,
                on_delete=self._delete_equipment,
            )
            self.equipment_table.setCellWidget(i, 5, actions)

    def _refresh_statuses(self):
        """Заполняет таблицу 'Статус' — брони со статусами."""
        rows = self.main.booking_repo.list_all()
        self.statuses_table.setRowCount(len(rows))
        for i, b in enumerate(rows):
            object_name = (b.hall.name if b.hall else "—")
            status_name = (b.status.name if b.status else "—")
            date_str = (
                b.start_datetime.strftime("%d.%m.%Y") if b.start_datetime else "—"
            )
            values = [
                str(b.booking_id),
                object_name,
                "Бронь",
                status_name,
                date_str,
            ]
            for j, v in enumerate(values):
                self.statuses_table.setItem(i, j, QTableWidgetItem(v))

            actions = self._make_action_buttons(
                b.booking_id,
                on_edit=self._edit_status,
                on_delete=self._delete_status,
            )
            self.statuses_table.setCellWidget(i, 5, actions)

    def _refresh_users(self):
        """Заполняет таблицу 'Пользователи'."""
        rows = self.main.user_repo.list_all()
        self.users_table.setRowCount(len(rows))
        for i, u in enumerate(rows):
            role_name = u.role.name if u.role else "—"
            # Email и дата регистрации — заглушки (в БД нет этих полей)
            values = [
                str(u.user_id),
                u.full_name or "—",
                f"user{u.user_id}@fs.booking",
                role_name,
                "Активен",
                "01.01.2026",
            ]
            for j, v in enumerate(values):
                self.users_table.setItem(i, j, QTableWidgetItem(v))

                actions = self._make_action_buttons(
                u.user_id,
                on_edit=self._edit_user,
                on_delete=self._delete_user,
            )
            self.users_table.setCellWidget(i, 6, actions)

    # ------- Действия -------

    def _on_add_click(self):
        """Нажатие на '+ Добавить …' — разное поведение для каждой вкладки."""
        if self.current_tab == "halls":
            self._add_hall()
        elif self.current_tab == "equipment":
            self._add_equipment()
        elif self.current_tab == "statuses":
            self.main.show_info("Добавление статусов — через справочник 'Залы'.")
        elif self.current_tab == "users":
            self.main.show_info("Регистрация пользователя — на экране входа.")

    def _add_hall(self):
        """Диалог создания зала."""
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
            except Exception as e:  # noqa: BLE001
                self.main.show_error(f"Ошибка: {e}")

    def _add_equipment(self):
        """Диалог создания оборудования."""
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
            except Exception as e:  # noqa: BLE001
                self.main.show_error(f"Ошибка: {e}")

    def _delete_hall(self, hall_id: int):
        if self.main.hall_repo.delete(hall_id):
            self._refresh_halls()

    def _delete_equipment(self, equipment_id: int):
        if self.main.equipment_repo.delete(equipment_id):
            self._refresh_equipment()

    def _delete_user(self, user_id: int):
        if self.main.user_repo.delete(user_id):
            self._refresh_users()

    def _edit_hall(self, hall_id: int):
        """Редактирование зала — упрощённо: только цена и описание."""
        hall = None
        for h in self.main.hall_repo.list_all():
            if h.hall_id == hall_id:
                hall = h
                break
        if not hall:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Зал #{hall_id}")
        form = QFormLayout(dlg)
        name = QLineEdit(hall.name)
        desc = QLineEdit(hall.description or "")
        price = QLineEdit(str(hall.price_per_hour))
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

    def _edit_equipment(self, equipment_id: int):
        """Редактирование оборудования: название, категория, цена, доступность."""
        eq = None
        for e in self.main.equipment_repo.list_all():
            if e.equipment_id == equipment_id:
                eq = e
                break
        if not eq:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Оборудование #{equipment_id}")
        form = QFormLayout(dlg)
        name = QLineEdit(eq.name)
        cat = QLineEdit(eq.category or "")
        price = QLineEdit(str(eq.price_per_day))
        available = QComboBox()
        available.addItem("Активен", True)
        available.addItem("Не активен", False)
        available.setCurrentIndex(0 if eq.is_available else 1)
        form.addRow("Название:", name)
        form.addRow("Категория:", cat)
        form.addRow("Цена/день:", price)
        form.addRow("Доступно:", available)
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
                    obj.is_available = available.currentData()
                    s.commit()
            self._refresh_equipment()

    def _edit_status(self, booking_id: int):
        """Изменение статуса брони."""
        statuses = self.main.status_repo.list_all()
        if not statuses:
            self.main.show_error("Нет доступных статусов.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Статус брони #{booking_id}")
        form = QFormLayout(dlg)
        combo = QComboBox()
        for st in statuses:
            combo.addItem(st.name, st.status_id)
        form.addRow("Новый статус:", combo)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec_() == QDialog.Accepted:
            with get_session() as s:
                obj = s.get(BookingORM, booking_id)
                if obj:
                    obj.status_id = combo.currentData()
                    s.commit()
            self._refresh_statuses()

    def _delete_status(self, booking_id: int):
        """Удаление брони — через подтверждение."""
        if self.main.booking_repo.delete(booking_id):
            self._refresh_statuses()

    def _edit_user(self, user_id: int):
        """Редактирование пользователя: ФИО и роль."""
        user = None
        for u in self.main.user_repo.list_all():
            if u.user_id == user_id:
                user = u
                break
        if not user:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Пользователь #{user_id}")
        form = QFormLayout(dlg)
        full_name = QLineEdit(user.full_name or "")
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

    def _make_action_buttons(self, obj_id: int, on_edit, on_delete) -> QWidget:
        """
        Создаёт виджет с двумя кнопками: «Ред» и «х».
        Возвращается для вставки в ячейку таблицы через setCellWidget.
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(3)

        edit_btn = QPushButton("Ред")
        edit_btn.setFixedSize(50, 26)
        edit_btn.setStyleSheet(
            "QPushButton { background-color:#B7C9D3; color:#2B2B2B; "
            "border:1px solid #8FA8B5; border-radius:4px; font-size:9pt; }"
            "QPushButton:hover { background-color:#A5B8C2; }"
        )
        edit_btn.clicked.connect(lambda _, oid=obj_id: on_edit(oid))
        layout.addWidget(edit_btn)

        del_btn = QPushButton("х")
        del_btn.setFixedSize(50, 26)
        del_btn.setStyleSheet(
            "QPushButton { background-color:#C97B7B; color:white; "
            "border:none; border-radius:4px; font-size:9pt; }"
            "QPushButton:hover { background-color:#A85F5F; }"
        )
        del_btn.clicked.connect(lambda _, oid=obj_id: on_delete(oid))
        layout.addWidget(del_btn)

        return widget

    def showEvent(self, event):
        """Обновляет данные при показе."""
        self._refresh_current_tab()
        super().showEvent(event)

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

        for w in (self.login_view, self.register_view, self.forgot_view,
                  self.client_profile_view, self.admin_profile_view,
                  self.calendar_view, self.booking_view, self.clients_view,
                  self.reports_view, self.references_hub_view):
            self.stack.addWidget(w)

        self.show_login()

    def show_login(self):
        """Показывает экран входа."""
        self.stack.setCurrentWidget(self.login_view)

    def show_register(self):
        """Показывает экран регистрации."""
        self.stack.setCurrentWidget(self.register_view)

    def show_forgot(self):
        """Показывает экран восстановления пароля."""
        self.stack.setCurrentWidget(self.forgot_view)

    def show_dashboard(self):
        """Открывает дашборд в зависимости от роли."""
        role = self.current_user.role.name.lower() if self.current_user else ""
        if "админ" in role or "admin" in role:
            self.stack.setCurrentWidget(self.admin_profile_view)
        else:
            self.stack.setCurrentWidget(self.client_profile_view)

    def show_view(self, view: QWidget):
        """Переключает активный экран."""
        self.stack.setCurrentWidget(view)

    def logout(self):
        """Выходит из системы и возвращает на экран входа."""
        self.current_user = None
        self.show_login()

    def show_error(self, text: str):
        """Показывает диалог ошибки."""
        QMessageBox.warning(self, "Ошибка", text)

    def show_info(self, text: str):
        """Показывает диалог с информацией."""
        QMessageBox.information(self, "Информация", text)


# =====================================================================
# ENTRY POINT
# =====================================================================

def main():
    """Инициализирует БД и запускает приложение."""
    import traceback

    def excepthook(exc_type, exc_value, exc_tb):
        """Печатает любую ошибку Python в консоль вместо тихого падения."""
        print("\n" + "=" * 60)
        print("ПОЙМАНО ИСКЛЮЧЕНИЕ:")
        traceback.print_exception(exc_type, exc_value, exc_tb)
        print("=" * 60 + "\n")

    sys.excepthook = excepthook

    seed_database()
    app = QApplication(sys.argv)

    from PyQt5.QtCore import qInstallMessageHandler

    def qt_msg_handler(msg_type, context, message):
        print(f"[Qt] {message}")

    qInstallMessageHandler(qt_msg_handler)

    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()