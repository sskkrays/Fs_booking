"""Настройка подключения к БД через SQLAlchemy."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session():
    """Возвращает новую сессию SQLAlchemy."""
    return SessionLocal()


def init_db() -> None:
    """Создаёт все таблицы, если их нет."""
    from src.data import orm_models  # noqa: F401
    Base.metadata.create_all(bind=engine)