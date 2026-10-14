"""Бизнес-правила приложения FS.Booking."""

import hashlib
import os
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from src.domain.exceptions import InvalidBookingPeriodError, ValidationError

PBKDF2_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    """Хеширует пароль через PBKDF2-HMAC-SHA256."""
    if not password:
        raise ValidationError("Пароль не может быть пустым.")
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Проверяет пароль против сохранённого хеша."""
    try:
        salt_hex, hash_hex = stored.split("$")
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return digest.hex() == hash_hex


def calculate_booking_price(start, end, price_per_hour, equipment_daily_prices=None):
    """Рассчитывает стоимость бронирования."""
    if end <= start:
        raise InvalidBookingPeriodError("Окончание должно быть позже начала.")
    hours = Decimal((end - start).total_seconds()) / Decimal(3600)
    total = hours * Decimal(price_per_hour)
    if equipment_daily_prices:
        total += sum(equipment_daily_prices, Decimal("0"))
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def normalize_phone(raw: str) -> str:
    """Приводит телефон к формату +7XXXXXXXXXX."""
    phone = (raw or "").strip()
    for ch in (" ", "-", "(", ")"):
        phone = phone.replace(ch, "")

    if re.fullmatch(r"\+7\d{10}", phone):
        return phone
    if re.fullmatch(r"8\d{10}", phone):
        return "+7" + phone[1:]

    raise ValidationError(
        "Неверный формат телефона. Допустимо: +79911148234 или 89911148235"
    )