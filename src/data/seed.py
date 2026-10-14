"""Заполнение БД начальными данными."""

from decimal import Decimal

from sqlalchemy import select

from src.data.database import get_session
from src.data.orm_models import (
    ClientORM,
    EquipmentORM,
    HallORM,
    RoleORM,
    StatusORM,
    TaskORM,
    UserORM,
)
from src.domain.services import hash_password


def seed_database() -> None:
    """
    Заполняет БД начальными данными при первом запуске.

    Создаёт:
    - роли (Администратор, Клиент);
    - статусы (Новая, Подтверждена, Отменена, Завершена, Не пришёл);
    - залы (Зал A, Зал B, Зал C);
    - оборудование (Проектор, Микрофон, Флипчарт);
    - пользователей (admin, client);
    - демо-клиентов;
    - демо-задачи.
    """
    with get_session() as s:
        # Роли
        if not s.scalar(select(RoleORM)):
            s.add_all([
                RoleORM(name="Администратор", description="Полный доступ"),
                RoleORM(name="Клиент", description="Ограниченный доступ"),
            ])
            s.commit()

        # Статусы
        if not s.scalar(select(StatusORM)):
            s.add_all([
                StatusORM(name="Новая"),
                StatusORM(name="Подтверждена"),
                StatusORM(name="Отменена"),
                StatusORM(name="Завершена"),
                StatusORM(name="Не пришёл"),
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
                UserORM(
                    role_id=admin_role.role_id,
                    login="admin",
                    password_hash=hash_password("admin123"),
                    full_name="Администратор Системы",
                ),
                UserORM(
                    role_id=client_role.role_id,
                    login="client",
                    password_hash=hash_password("client123"),
                    full_name="Иван Иванов",
                ),
            ])
            s.commit()

        # Демо-клиенты
        if not s.scalar(select(ClientORM)):
            s.add_all([
                ClientORM(name="ООО Ромашка", phone="+79000000001",
                          email="info@romashka.ru", notes="VIP"),
                ClientORM(name="ИП Петров", phone="+79000000002",
                          email="petrov@mail.ru"),
            ])
            s.commit()

        # Демо-задачи
        if not s.scalar(select(TaskORM)):
            s.add_all([
                TaskORM(text="Собрать статистику по брони и выручке"),
                TaskORM(text="Клиент не отвечает на уточнение по редакции"),
                TaskORM(text="Перегорела лампа в постоянном свете"),
                TaskORM(text="Не работает кондиционер в зале 'Лофт'"),
                TaskORM(text="Не хватает базовых расходников"),
            ])
            s.commit()