"""ORM-модели, соответствующие ER-диаграмме FS.Booking."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from src.data.database import Base


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
    """Задача для панели администратора."""
    __tablename__ = "task"
    task_id = Column(Integer, primary_key=True)
    text = Column(String(500), nullable=False)
    is_done = Column(Boolean, default=False)