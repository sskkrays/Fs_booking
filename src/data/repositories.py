"""CRUD-операции для сущностей FS.Booking. Только ORM, без SQL-инъекций."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select

from src.data.database import get_session
from src.data.orm_models import (
    BookingEquipmentORM,
    BookingORM,
    ClientORM,
    EquipmentORM,
    HallORM,
    RoleORM,
    StatusORM,
    TaskORM,
    UserORM,
)


class ClientRepository:
    """CRUD-операции для клиентов."""

    def auto_update_statuses(self) -> None:
        """
        Автоматически обновляет статусы:
        - Новая → Отменена, если прошло 15 минут без предоплаты.
        - Подтверждена → Не явился, если бронь завершилась (время окончания прошло).
        """
        from datetime import datetime, timedelta
        from src.data.orm_models import StatusORM

        now = datetime.now()

        with get_session() as s:
            # Находим статусы
            status_new = s.scalar(select(StatusORM).where(StatusORM.name == "Новая"))
            status_confirmed = s.scalar(
                select(StatusORM).where(StatusORM.name == "Подтверждена")
            )
            status_cancelled = s.scalar(
                select(StatusORM).where(StatusORM.name == "Отменена")
            )
            status_no_show = s.scalar(
                select(StatusORM).where(StatusORM.name == "Не явился")
            )

            # 1. Новая → Отменена через 15 минут
            if status_new and status_cancelled:
                bookings_new = list(
                    s.scalars(
                        select(BookingORM).where(BookingORM.status_id == status_new.status_id)
                    ).all()
                )
                for b in bookings_new:
                    # Если прошло больше 15 минут с создания
                    if b.payment_due is not None and b.payment_due < now:
                        b.status_id = status_cancelled.status_id

            # 2. Подтверждена → Не явился, если бронь завершилась
            if status_confirmed and status_no_show:
                bookings_confirmed = list(
                    s.scalars(
                        select(BookingORM).where(
                            BookingORM.status_id == status_confirmed.status_id
                        )
                    ).all()
                )
                for b in bookings_confirmed:
                    if b.end_datetime < now:
                        b.status_id = status_no_show.status_id

            s.commit()

    def create(self, name="", phone="", email="", notes="") -> ClientORM:
        """Создаёт нового клиента."""
        with get_session() as s:
            obj = ClientORM(name=name, phone=phone, email=email, notes=notes)
            s.add(obj)
            s.commit()
            s.refresh(obj)
            return obj

    def confirm_prepayment(self, booking_id: int) -> bool:
        """Подтверждает бронь — вносит предоплату 15%."""
        from decimal import Decimal
        from src.data.orm_models import StatusORM

        with get_session() as s:
            obj = s.get(BookingORM, booking_id)
            if not obj:
                return False

            status = s.scalar(
                select(StatusORM).where(StatusORM.name == "Подтверждена")
            )
            if status:
                obj.status_id = status.status_id

            # Предоплата 15%
            obj.prepayment = (Decimal(obj.total_price) * Decimal("0.15")).quantize(
                Decimal("0.01")
            )
            s.commit()
            return True

    def complete_booking(self, booking_id: int) -> bool:
        """Завершает бронь — клиент оплатил остаток."""
        from src.data.orm_models import StatusORM

        with get_session() as s:
            obj = s.get(BookingORM, booking_id)
            if not obj:
                return False
            status = s.scalar(
                select(StatusORM).where(StatusORM.name == "Завершена")
            )
            if status:
                obj.status_id = status.status_id
                s.commit()
                return True
            return False

    def mark_no_show(self, booking_id: int) -> bool:
        """Помечает бронь как 'Не явился'."""
        from src.data.orm_models import StatusORM

        with get_session() as s:
            obj = s.get(BookingORM, booking_id)
            if not obj:
                return False
            status = s.scalar(
                select(StatusORM).where(StatusORM.name == "Не явился")
            )
            if status:
                obj.status_id = status.status_id
                s.commit()
                return True
            return False

    def cancel_booking(self, booking_id: int) -> bool:
        """Отменяет бронь."""
        from src.data.orm_models import StatusORM

        with get_session() as s:
            obj = s.get(BookingORM, booking_id)
            if not obj:
                return False
            status = s.scalar(
                select(StatusORM).where(StatusORM.name == "Отменена")
            )
            if status:
                obj.status_id = status.status_id
                s.commit()
                return True
            return False

    def list_all(self, search="") -> list[ClientORM]:
        """Возвращает список клиентов с фильтром по имени."""
        with get_session() as s:
            stmt = select(ClientORM).order_by(ClientORM.name)
            all_clients = list(s.scalars(stmt).all())

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
            s.commit()
            s.refresh(obj)
            return obj

    def delete(self, client_id: int) -> bool:
        """Удаляет клиента по ID."""
        with get_session() as s:
            obj = s.get(ClientORM, client_id)
            if not obj:
                return False
            s.delete(obj)
            s.commit()
            return True


class HallRepository:
    """CRUD-операции для залов."""

    def create(self, name, description, price_per_hour) -> HallORM:
        with get_session() as s:
            obj = HallORM(name=name, description=description, price_per_hour=price_per_hour)
            s.add(obj)
            s.commit()
            s.refresh(obj)
            return obj

    def list_all(self, only_active=False) -> list[HallORM]:
        with get_session() as s:
            stmt = select(HallORM)
            if only_active:
                stmt = stmt.where(HallORM.is_active.is_(True))
            return list(s.scalars(stmt).all())

    def get(self, hall_id: int) -> HallORM | None:
        with get_session() as s:
            return s.get(HallORM, hall_id)

    def update(self, hall_id: int, **fields) -> HallORM | None:
        allowed = {"name", "description", "price_per_hour", "is_active"}
        with get_session() as s:
            obj = s.get(HallORM, hall_id)
            if not obj:
                return None
            for k, v in fields.items():
                if k in allowed:
                    setattr(obj, k, v)
            s.commit()
            s.refresh(obj)
            return obj

    def delete(self, hall_id: int) -> bool:
        with get_session() as s:
            obj = s.get(HallORM, hall_id)
            if not obj:
                return False
            s.delete(obj)
            s.commit()
            return True


class EquipmentRepository:
    """CRUD-операции для оборудования."""

    def create(self, name, category, price_per_day) -> EquipmentORM:
        with get_session() as s:
            obj = EquipmentORM(name=name, category=category, price_per_day=price_per_day)
            s.add(obj)
            s.commit()
            s.refresh(obj)
            return obj

    def list_all(self) -> list[EquipmentORM]:
        with get_session() as s:
            return list(s.scalars(select(EquipmentORM)).all())

    def delete(self, equipment_id: int) -> bool:
        with get_session() as s:
            obj = s.get(EquipmentORM, equipment_id)
            if not obj:
                return False
            s.delete(obj)
            s.commit()
            return True

    def toggle_available(self, equipment_id: int) -> bool:
        """Переключает доступность оборудования."""
        with get_session() as s:
            obj = s.get(EquipmentORM, equipment_id)
            if not obj:
                return False
            obj.is_available = not obj.is_available
            s.commit()
            return True


class StatusRepository:
    """CRUD-операции для статусов."""

    def list_all(self) -> list[StatusORM]:
        with get_session() as s:
            return list(s.scalars(select(StatusORM)).all())

    def create(self, name) -> StatusORM:
        with get_session() as s:
            obj = StatusORM(name=name)
            s.add(obj)
            s.commit()
            s.refresh(obj)
            return obj


class UserRepository:
    """CRUD-операции для пользователей."""

    def create(self, role_id, login, password_hash, full_name) -> UserORM:
        with get_session() as s:
            obj = UserORM(
                role_id=role_id,
                login=login,
                password_hash=password_hash,
                full_name=full_name,
            )
            s.add(obj)
            s.commit()
            s.refresh(obj)
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
            s.delete(obj)
            s.commit()
            return True


class BookingRepository:
    """CRUD-операции для броней."""

    def create(
        self,
        client_id,
        hall_id,
        user_id,
        start,
        end,
        status_id,
        total_price,
        equipment_ids=None,
    ) -> BookingORM:
        with get_session() as s:
            obj = BookingORM(
                client_id=client_id,
                hall_id=hall_id,
                user_id=user_id,
                start_datetime=start,
                end_datetime=end,
                status_id=status_id,
                total_price=total_price,
            )
            s.add(obj)
            s.flush()
            for eq_id in equipment_ids or []:
                s.add(
                    BookingEquipmentORM(
                        booking_id=obj.booking_id,
                        equipment_id=eq_id,
                        quantity=1,
                    )
                )
            s.commit()
            s.refresh(obj)
            return obj

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
        """Возвращает брони за указанный день."""
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

    def update_status(self, booking_id: int, status_id: int) -> bool:
        """Меняет статус брони по ID."""
        with get_session() as s:
            obj = s.get(BookingORM, booking_id)
            if not obj:
                return False
            obj.status_id = status_id
            s.commit()
            return True

    def delete(self, booking_id: int) -> bool:
        with get_session() as s:
            obj = s.get(BookingORM, booking_id)
            if not obj:
                return False
            s.delete(obj)
            s.commit()
            return True

    def revenue_report(self) -> dict:
        """KPI + разбивка выручки по залам."""
        with get_session() as s:
            total = s.scalar(
                select(func.coalesce(func.sum(BookingORM.total_price), 0))
            ) or 0
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


class TaskRepository:
    """CRUD для задач в блоке 'Ожидания решений'."""

    def list_all(self) -> list[TaskORM]:
        with get_session() as s:
            return list(s.scalars(select(TaskORM).order_by(TaskORM.task_id)).all())

    def create(self, text: str) -> TaskORM:
        with get_session() as s:
            obj = TaskORM(text=text)
            s.add(obj)
            s.commit()
            s.refresh(obj)
            return obj

    def delete(self, task_id: int) -> bool:
        with get_session() as s:
            obj = s.get(TaskORM, task_id)
            if not obj:
                return False
            s.delete(obj)
            s.commit()
            return True