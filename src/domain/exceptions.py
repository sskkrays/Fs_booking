"""Кастомные исключения доменного слоя FS.Booking."""


class DomainError(Exception):
    """Базовое исключение для бизнес-логики."""


class InvalidBookingPeriodError(DomainError):
    """Окончание брони раньше начала."""


class ValidationError(DomainError):
    """Ошибка валидации входных данных."""


class AuthenticationError(DomainError):
    """Ошибка аутентификации."""