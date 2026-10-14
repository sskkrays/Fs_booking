"""Диалог создания брони с ограничением рабочих часов и валидацией."""

from decimal import Decimal

from PyQt5.QtCore import QDate, QDateTime, QTime, Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)
from sqlalchemy import select

from src.data.database import get_session
from src.data.orm_models import EquipmentORM, HallORM, StatusORM, BookingORM
from src.domain.exceptions import InvalidBookingPeriodError
from src.domain.services import calculate_booking_price


# Рабочие часы фотостудии
WORK_START_HOUR = 8
WORK_END_HOUR = 19
LAST_START_HOUR = 18          # последняя запись может начаться в 18:30
LAST_START_MINUTE = 30
SLOT_MINUTES = 30             # шаг занятости — 30 минут


class BookingDialog(QDialog):


    # ---------- Построение ----------

    def _build(self):
        """Собирает форму: клиент, зал, дата, время, оборудование."""
        root = QVBoxLayout(self)
        form = QFormLayout()

        # ---------- Клиент ----------
        self.client_input = QLineEdit()
        user = self.main.current_user
        is_admin = bool(user and user.role_id == 1)
        if is_admin:
            self.client_input.setPlaceholderText("Введите имя клиента")
        else:
            self.client_input.setText(user.full_name)
            self.client_input.setReadOnly(True)

        # ---------- Зал ----------
        self.hall_combo = QComboBox()
        for h in self.main.hall_repo.list_all(only_active=True):
            self.hall_combo.addItem(
                f"{h.name} ({h.price_per_hour} ₽/ч)", h.hall_id
            )
        self.hall_combo.currentIndexChanged.connect(self._refresh_all)

        # ---------- Дата ----------
        self.date_edit = QDateEdit()
        today = QDate.currentDate()
        self.date_edit.setDate(today)
        self.date_edit.setMinimumDate(today)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_edit.dateChanged.connect(self._refresh_all)

        # ---------- Начало ----------
        self.start_hour = QComboBox()
        self.start_minute = QComboBox()

        start_time_row = QHBoxLayout()
        start_time_row.addWidget(QLabel("Час:"))
        start_time_row.addWidget(self.start_hour)
        start_time_row.addWidget(QLabel("Мин:"))
        start_time_row.addWidget(self.start_minute)
        start_time_row.addStretch()

        self.start_hour.currentIndexChanged.connect(self._on_start_changed)
        self.start_minute.currentIndexChanged.connect(self._on_start_changed)

        # ---------- Окончание ----------
        self.end_hour = QComboBox()
        self.end_minute = QComboBox()

        end_time_row = QHBoxLayout()
        end_time_row.addWidget(QLabel("Час:"))
        end_time_row.addWidget(self.end_hour)
        end_time_row.addWidget(QLabel("Мин:"))
        end_time_row.addWidget(self.end_minute)
        end_time_row.addStretch()

        # Одинаковая ширина всех комбобоксов времени
        for combo in (self.start_hour, self.start_minute,
                      self.end_hour, self.end_minute):
            combo.setFixedWidth(80)

        # ---------- Быстрые кнопки ----------
        shortcuts_row = QHBoxLayout()
        shortcuts_row.setSpacing(6)
        for label, minutes in (("+30 мин", 30), ("+1 час", 60), ("+2 часа", 120)):
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda _, m=minutes: self._extend_end(m))
            shortcuts_row.addWidget(btn)
        shortcuts_row.addStretch()

        # ---------- Список занятых слотов ----------
        self.busy_list = QListWidget()
        self.busy_list.setMaximumHeight(140)
        self.busy_list.setStyleSheet(
            "QListWidget { background-color:#FDF6E3; border:1px solid #C8D4DA; "
            "border-radius:6px; padding:4px; font-size:10pt; }"
        )

        # ---------- Оборудование ----------
        self.equip_combo = QComboBox()
        self.equip_combo.addItem("— без оборудования —", None)
        for e in self.main.equipment_repo.list_all():
            if e.is_available:
                self.equip_combo.addItem(
                    f"{e.name} ({e.price_per_day} ₽)", e.equipment_id
                )

        # ---------- Итоговая стоимость ----------
        self.total_label = QLabel("0.00 ₽")
        self.total_label.setStyleSheet(
            "font-size:16pt; font-weight:bold; color:#2B2B2B; "
            "background-color:#FDF6E3; border:1px solid #C8D4DA; "
            "border-radius:6px; padding:8px 14px;"
        )
        self.total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # ---------- Сборка формы ----------
        form.addRow("Клиент:", self.client_input)
        form.addRow("Зал:", self.hall_combo)
        form.addRow("Дата:", self.date_edit)
        form.addRow("Начало:", start_time_row)
        form.addRow("Окончание:", end_time_row)
        form.addRow("Быстро:", shortcuts_row)
        form.addRow("Оборудование:", self.equip_combo)
        form.addRow("Итоговая стоимость:", self.total_label)

        root.addLayout(form)

        # ---------- Информация о рабочих часах ----------
        info = QLabel(
            f"⏰ Работаем с {WORK_START_HOUR}:00 до {WORK_END_HOUR}:00. "
            f"Последняя запись — не позже "
            f"{LAST_START_HOUR}:{LAST_START_MINUTE:02d}."
        )
        info.setStyleSheet(
            "color:#2B2B2B; background-color:#E8D9B8; padding:6px 10px; "
            "border-radius:6px; font-size:10pt;"
        )
        info.setWordWrap(True)
        root.addWidget(info)

        # ---------- Заголовок «Занятые слоты» ----------
        busy_label = QLabel("Занятые слоты в выбранный день:")
        busy_label.setStyleSheet(
            "font-weight:bold; font-size:10pt; margin-top:6px;"
        )
        root.addWidget(busy_label)
        root.addWidget(self.busy_list)

        # ---------- Кнопки ОК / Cancel ----------
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.setWindowTitle("Новая бронь")
        self.setMinimumWidth(520)
        self._busy_slots = []          # список (start_dt, end_dt) занятых
        self._build()
        self._refresh_all()

    def _on_end_hour_changed(self):
        """При выборе часа 19 — минуты только 00."""
        end_h = self.end_hour.currentData()
        current_m = self.end_minute.currentData()

        if end_h is not None and end_h >= WORK_END_HOUR:
            # Оставляем только 00
            self.end_minute.blockSignals(True)
            self.end_minute.clear()
            self.end_minute.addItem("00", 0)
            self.end_minute.setCurrentIndex(0)
            self.end_minute.blockSignals(False)
        else:
            # Восстанавливаем 00 и 30
            self.end_minute.blockSignals(True)
            current_text = self.end_minute.currentText()
            self.end_minute.clear()
            self.end_minute.addItem("00", 0)
            self.end_minute.addItem("30", 30)

            # Восстанавливаем выбор, если возможно
            idx = self.end_minute.findData(current_m)
            if idx >= 0:
                self.end_minute.setCurrentIndex(idx)
            self.end_minute.blockSignals(False)

        

        

        # ---------- Информация о часах ----------
        info = QLabel(
            f"⏰ Работаем с {WORK_START_HOUR}:00 до {WORK_END_HOUR}:00. "
            f"Последняя запись — не позже {LAST_START_HOUR}:{LAST_START_MINUTE:02d}."
        )
        info.setStyleSheet(
            "color:#2B2B2B; background-color:#E8D9B8; padding:6px 10px; "
            "border-radius:6px; font-size:10pt;"
        )
        info.setWordWrap(True)
        root.addWidget(info)

        busy_label = QLabel("Занятые слоты в выбранный день:")
        busy_label.setStyleSheet("font-weight:bold; font-size:10pt; margin-top:6px;")
        root.addWidget(busy_label)
        root.addWidget(self.busy_list)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ---------- Работа с занятыми слотами ----------

    def _get_busy_slots(self):
        """Возвращает список (start_dt, end_dt) актуальных занятых слотов."""
        hall_id = self.hall_combo.currentData()
        if hall_id is None:
            return []

        day = self.date_edit.date()
        start_day = QDateTime(day, QTime(0, 0)).toPyDateTime()
        end_day = QDateTime(day, QTime(23, 59, 59)).toPyDateTime()

        with get_session() as s:
            stmt = (
                select(BookingORM)
                .where(
                    BookingORM.hall_id == hall_id,
                    BookingORM.start_datetime >= start_day,
                    BookingORM.start_datetime <= end_day,
                )
                .order_by(BookingORM.start_datetime)
            )
            bookings = list(s.scalars(stmt).all())

        # --- Фильтр: если сегодня и слот уже прошёл — не показываем ---
        today = QDate.currentDate()
        is_today = day == today
        now = QDateTime.currentDateTime().toPyDateTime()

        result = []
        for b in bookings:
            if is_today and b.end_datetime < now:
                # слот полностью в прошлом — пропускаем
                continue
            result.append((b.start_datetime, b.end_datetime))

        return result

    def _refresh_all(self):
        """Обновляет занятые слоты, доступные часы и список."""
        self._busy_slots = self._get_busy_slots()
        self._update_busy_list()
        self._update_available_hours()
        self._update_total()

    def _update_busy_list(self):
        """Отображает занятые слоты в списке."""
        self.busy_list.clear()

        if not self._busy_slots:
            self.busy_list.addItem("— все слоты свободны —")
            return

        for start, end in self._busy_slots:
            item_text = f"● {start.strftime('%H:%M')} — {end.strftime('%H:%M')}"
            item = QListWidgetItem(item_text)
            item.setForeground(Qt.red)
            self.busy_list.addItem(item)

            # --- Начало: от 8:00 до 18:30 ---
        self.start_hour.blockSignals(True)
        self.start_minute.blockSignals(True)
        current_start_h = self.start_hour.currentData()
        current_start_m = self.start_minute.currentData()
        self.start_hour.clear()
        self.start_minute.clear()

        # Проверяем, сегодняшняя ли дата
        selected_date = self.date_edit.date()
        today = QDate.currentDate()
        is_today = selected_date == today
        now = QDateTime.currentDateTime()
        now_h = now.time().hour()
        now_m = now.time().minute()

        for h in range(WORK_START_HOUR, LAST_START_HOUR + 1):
            # Если сегодня и час уже прошёл (или текущий час, но минут 30 уже наступило)
            if is_today:
                if h < now_h:
                    continue
                if h == now_h and now_m >= 30:
                    # текущий час уже прошёл полностью — пропускаем и его
                    if h < LAST_START_HOUR:
                        continue
            self.start_hour.addItem(f"{h:02d}", h)

        # Минуты начала
        for m in (0, 30):
            self.start_minute.addItem(f"{m:02d}", m)

        # восстанавливаем выбор
        if current_start_h is not None:
            idx = self.start_hour.findData(current_start_h)
            if idx >= 0:
                self.start_hour.setCurrentIndex(idx)
        if current_start_m is not None:
            idx = self.start_minute.findData(current_start_m)
            if idx >= 0:
                self.start_minute.setCurrentIndex(idx)

        self.start_hour.blockSignals(False)
        self.start_minute.blockSignals(False)

        # --- Окончание: часы + минуты, зависят от выбранного начала ---
        self._update_end_hours()

    def _update_end_hours(self):
        """Часы и минуты окончания зависят от выбранного начала."""
        self.end_hour.blockSignals(True)
        self.end_minute.blockSignals(True)

        current_end_h = self.end_hour.currentData()
        current_end_m = self.end_minute.currentData()

        start_h = self.start_hour.currentData()
        start_m = self.start_minute.currentData()

        if start_h is None or start_m is None:
            start_h, start_m = WORK_START_HOUR, 0

        self.end_hour.clear()
        self.end_minute.clear()

        # Часы окончания — от start_h до WORK_END_HOUR
        for h in range(start_h, WORK_END_HOUR + 1):
            self.end_hour.addItem(f"{h:02d}", h)

        # Минуты окончания — 00 и 30, но:
        # - для последнего часа (19) — только 00
        # - для 18 — 00 и 30, но не больше 19:00 (т.е. 18:30 — последний слот начала, окончание может быть 19:00)
        for m in (0, 30):
            if h == WORK_END_HOUR and m > 0:
                # Для 19:00 минуты только 00
                continue
            self.end_minute.addItem(f"{m:02d}", m)

        # Восстанавливаем выбор часа
        if current_end_h is not None and current_end_h >= start_h:
            idx = self.end_hour.findData(current_end_h)
            if idx >= 0:
                self.end_hour.setCurrentIndex(idx)
        else:
            # По умолчанию окончание = начало + 1 час
            target_h = min(start_h + 1, WORK_END_HOUR)
            idx = self.end_hour.findData(target_h)
            if idx >= 0:
                self.end_hour.setCurrentIndex(idx)

        # Восстанавливаем выбор минуты
        if current_end_m is not None:
            idx = self.end_minute.findData(current_end_m)
            if idx >= 0:
                self.end_minute.setCurrentIndex(idx)

        # --- НОВОЕ: отсекаем минуты, которые не больше начала ---
        self._fix_end_after_start()

        self.end_hour.blockSignals(False)
        self.end_minute.blockSignals(False)

    def _update_available_hours(self):
        """Заполняет часы начала и окончания только доступными вариантами."""
        # --- Начало: от 8:00 до 18:30, с учётом сегодняшнего времени ---
        self.start_hour.blockSignals(True)
        self.start_minute.blockSignals(True)

        current_start_h = self.start_hour.currentData()
        current_start_m = self.start_minute.currentData()

        self.start_hour.clear()
        self.start_minute.clear()

        selected_date = self.date_edit.date()
        today = QDate.currentDate()
        is_today = selected_date == today
        now = QDateTime.currentDateTime()
        now_h = now.time().hour()
        now_m = now.time().minute()

        # Если сегодня и уже позже 18:30 — предлагаем завтра
        if is_today and (
            now_h > LAST_START_HOUR
            or (now_h == LAST_START_HOUR and now_m > LAST_START_MINUTE)
        ):
            # Убираем блокировку сигналов, чтобы смена даты сработала
            self.start_hour.blockSignals(False)
            self.start_minute.blockSignals(False)
            self.end_hour.blockSignals(False)
            self.end_minute.blockSignals(False)

            # Автоматически переключаем дату на завтра
            tomorrow = today.addDays(1)
            self.date_edit.blockSignals(True)
            self.date_edit.setDate(tomorrow)
            self.date_edit.blockSignals(False)

            # Пересчитываем доступные часы для завтра
            self._update_available_hours()
            return

        for h in range(WORK_START_HOUR, LAST_START_HOUR + 1):
            if is_today:
                if h < now_h:
                    continue
                if h == now_h and now_m >= 30:
                    if h < LAST_START_HOUR:
                        continue
            self.start_hour.addItem(f"{h:02d}", h)

        for m in (0, 30):
            self.start_minute.addItem(f"{m:02d}", m)

        if current_start_h is not None:
            idx = self.start_hour.findData(current_start_h)
            if idx >= 0:
                self.start_hour.setCurrentIndex(idx)

        if current_start_m is not None:
            idx = self.start_minute.findData(current_start_m)
            if idx >= 0:
                self.start_minute.setCurrentIndex(idx)

        self.start_hour.blockSignals(False)
        self.start_minute.blockSignals(False)

        # --- Окончание ---
        self._update_end_hours()

    def _update_end_hours(self):
        """Часы и минуты окончания зависят от выбранного начала."""
        self.end_hour.blockSignals(True)
        self.end_minute.blockSignals(True)

        current_end_h = self.end_hour.currentData()
        current_end_m = self.end_minute.currentData()

        start_h = self.start_hour.currentData()
        start_m = self.start_minute.currentData()

        if start_h is None or start_m is None:
            start_h, start_m = WORK_START_HOUR, 0

        self.end_hour.clear()
        self.end_minute.clear()

        for h in range(start_h, WORK_END_HOUR + 1):
            self.end_hour.addItem(f"{h:02d}", h)

        # Минуты окончания: 
        # - если час окончания < 19 → 00 и 30
        # - если час окончания = 19 → только 00
        end_h = self.end_hour.currentData()
        self.end_minute.clear()

        if end_h is not None and end_h >= WORK_END_HOUR:
            self.end_minute.addItem("00", 0)
        else:
            for m in (0, 30):
                self.end_minute.addItem(f"{m:02d}", m)

        if current_end_h is not None and current_end_h >= start_h:
            idx = self.end_hour.findData(current_end_h)
            if idx >= 0:
                self.end_hour.setCurrentIndex(idx)
        else:
            target_h = min(start_h + 1, WORK_END_HOUR)
            idx = self.end_hour.findData(target_h)
            if idx >= 0:
                self.end_hour.setCurrentIndex(idx)

        if current_end_m is not None:
            idx = self.end_minute.findData(current_end_m)
            if idx >= 0:
                self.end_minute.setCurrentIndex(idx)

        self._fix_end_after_start()

        self.end_hour.blockSignals(False)
        self.end_minute.blockSignals(False)

    def _fix_end_after_start(self):
        """Окончание: не раньше начала+30 мин и не позже 19:00."""
        start_h = self.start_hour.currentData()
        start_m = self.start_minute.currentData()
        end_h = self.end_hour.currentData()
        end_m = self.end_minute.currentData()

        if None in (start_h, start_m, end_h, end_m):
            return

        start_total = start_h * 60 + start_m
        end_total = end_h * 60 + end_m
        max_total = WORK_END_HOUR * 60        # 19:00 = 1140 минут

        # Окончание минимум +30 минут
        if end_total <= start_total:
            end_total = start_total + 30

        # Окончание не позже 19:00
        if end_total > max_total:
            end_total = max_total

        new_h = end_total // 60
        new_m = end_total % 60

        # Для 19:00 — только минуты 00
        if new_h == WORK_END_HOUR:
            new_m = 0

        idx_h = self.end_hour.findData(new_h)
        if idx_h >= 0:
            self.end_hour.setCurrentIndex(idx_h)

        idx_m = self.end_minute.findData(new_m)
        if idx_m >= 0:
            self.end_minute.setCurrentIndex(idx_m)
        elif new_m == 0:
            # Если минуты 00 нет в списке — добавим
            self.end_minute.addItem("00", 0)
            self.end_minute.setCurrentIndex(self.end_minute.findData(0))

        self._update_total()

    def _update_total(self):
        """Пересчитывает стоимость и отображает её в диалоге."""
        try:
            hall_id = self.hall_combo.currentData()
            if hall_id is None:
                return

            start_h = self.start_hour.currentData()
            start_m = self.start_minute.currentData()
            end_h = self.end_hour.currentData()
            end_m = self.end_minute.currentData()

            if None in (start_h, start_m, end_h, end_m):
                return

            day = self.date_edit.date()
            start = QDateTime(day, QTime(start_h, start_m)).toPyDateTime()
            end = QDateTime(day, QTime(end_h, end_m)).toPyDateTime()

            if end <= start:
                self.total_label.setText("—")
                return

            # Цена зала
            with get_session() as s:
                hall = s.get(HallORM, hall_id)
            if not hall:
                return
            price = Decimal(hall.price_per_hour)

            # Цена оборудования
            eq_prices = []
            eq_id = self.equip_combo.currentData()
            if eq_id is not None:
                with get_session() as s:
                    eq = s.get(EquipmentORM, eq_id)
                if eq:
                    eq_prices.append(Decimal(eq.price_per_day))

            total = calculate_booking_price(start, end, price, eq_prices)
            self.total_label.setText(f"{total:.2f} ₽")

        except Exception:
            self.total_label.setText("—")


    def _on_start_changed(self):
        """При изменении начала — обновляет часы окончания и стоимость."""
        self._update_end_hours()
        self._update_total()

    def _extend_end(self, minutes):
        """Прибавляет минуты к окончанию."""
        h = self.end_hour.currentData()
        m = self.end_minute.currentData()
        if h is None or m is None:
            return

        total = h * 60 + m + minutes
        new_h = total // 60
        new_m = total % 60

        if new_h > WORK_END_HOUR:
            new_h = WORK_END_HOUR
            new_m = 0

        idx_h = self.end_hour.findData(new_h)
        if idx_h >= 0:
            self.end_hour.setCurrentIndex(idx_h)
        idx_m = self.end_minute.findData(new_m)
        if idx_m >= 0:
            self.end_minute.setCurrentIndex(idx_m)
            self._update_total()

    # ---------- Сохранение ----------

    def _on_save(self):
        """Сохраняет бронь с полной валидацией."""
        try:
            # ---------- 1. Проверка клиента ----------
            client_name = self.client_input.text().strip()
            if not client_name:
                self.main.show_error("Введите имя клиента.")
                return

            all_clients = self.main.client_repo.list_all()
            needle = client_name.lower()
            existing = next(
                (c for c in all_clients if (c.name or "").lower() == needle),
                None,
            )
            if existing is not None:
                client_id = existing.client_id
            else:
                new_client = self.main.client_repo.create(
                    name=client_name, phone="", email="", notes=""
                )
                client_id = new_client.client_id

            # ---------- 2. Собираем дату и время ----------
            hall_id = self.hall_combo.currentData()

            day = self.date_edit.date()
            start_h = self.start_hour.currentData()
            start_m = self.start_minute.currentData()
            end_h = self.end_hour.currentData()
            end_m = self.end_minute.currentData()

            if None in (start_h, start_m, end_h, end_m):
                self.main.show_error(
                    "Выберите корректное время начала и окончания. "
                    "Возможно, сегодня уже нельзя забронировать — рабочий день "
                    "до 19:00, последняя запись в 18:30."
                )
                return

            start = QDateTime(day, QTime(start_h, start_m)).toPyDateTime()
            end = QDateTime(day, QTime(end_h, end_m)).toPyDateTime()

            # ---------- 3. Валидация времени ----------

            # 3.0. Если бронь на сегодня — начало должно быть в будущем
            now = QDateTime.currentDateTime().toPyDateTime()
            if start.date() == now.date() and start <= now:
                self.main.show_error(
                    f"Нельзя бронировать на прошедшее время "
                    f"(сейчас {now.strftime('%H:%M')})."
                )
                return

            # 3.1. Окончание позже начала
            if end <= start:
                self.main.show_error("Окончание должно быть позже начала.")
                return

            # 3.1. Окончание позже начала
            if end <= start:
                self.main.show_error("Окончание должно быть позже начала.")
                return

            # 3.2. Начало не раньше 8:00
            if start.hour < WORK_START_HOUR:
                self.main.show_error(
                    f"Начало работы — не раньше {WORK_START_HOUR}:00."
                )
                return

            # 3.3. Последняя запись — не позже 18:30
            if start.hour > LAST_START_HOUR or (
                start.hour == LAST_START_HOUR and start.minute > LAST_START_MINUTE
            ):
                self.main.show_error(
                    f"Последняя запись — не позже "
                    f"{LAST_START_HOUR}:{LAST_START_MINUTE:02d}."
                )
                return

            # 3.4. Окончание — строго до 19:00
            if end.hour > WORK_END_HOUR or (
                end.hour == WORK_END_HOUR and end.minute > 0
            ):
                self.main.show_error(
                    f"Окончание — не позже {WORK_END_HOUR}:00."
                )
                return

            # 3.5. Нельзя бронировать в прошлом
            now = QDateTime.currentDateTime().toPyDateTime()
            if start < now:
                self.main.show_error(
                    f"Нельзя бронировать на прошедшее время "
                    f"(сейчас {now.strftime('%H:%M')})."
                )
                return

            # 3.6. Если бронь на сегодня — окончание должно быть в будущем
            if start.date() == now.date() and end < now:
                self.main.show_error("Окончание брони уже прошло.")
                return

            # ---------- 4. Проверка пересечения с другими бронями ----------
            with get_session() as s:
                stmt = select(BookingORM).where(
                    BookingORM.hall_id == hall_id,
                    BookingORM.start_datetime < end,
                    BookingORM.end_datetime > start,
                )
                conflict = s.scalar(stmt)
                if conflict:
                    self.main.show_error(
                        f"Этот слот занят другой бронью "
                        f"({conflict.start_datetime.strftime('%H:%M')} — "
                        f"{conflict.end_datetime.strftime('%H:%M')})."
                    )
                    return

            # ---------- 5. Расчёт стоимости ----------
            with get_session() as s:
                hall = s.get(HallORM, hall_id)
            if not hall:
                self.main.show_error("Зал не найден.")
                return
            price = Decimal(hall.price_per_hour)

            eq_id = self.equip_combo.currentData()
            eq_prices = []
            if eq_id is not None:
                with get_session() as s:
                    eq = s.get(EquipmentORM, eq_id)
                if eq:
                    eq_prices.append(Decimal(eq.price_per_day))

            total = calculate_booking_price(start, end, price, eq_prices)

            # ---------- 6. Получаем статус «Новая» ----------
            with get_session() as s:
                status = s.scalar(select(StatusORM).where(StatusORM.name == "Новая"))
                status_id = status.status_id if status else 1

            # ---------- 7. Сохраняем бронь ----------
            self.main.booking_repo.create(
                client_id=client_id,
                hall_id=hall_id,
                user_id=self.main.current_user.user_id,
                start=start,
                end=end,
                status_id=status_id,
                total_price=total,
                equipment_ids=[eq_id] if eq_id else [],
            )
            self.main.show_info(f"Бронь создана. Стоимость: {total} ₽")
            self.accept()

        except InvalidBookingPeriodError as e:
            self.main.show_error(str(e))
        except Exception as e:
            self.main.show_error(f"Ошибка: {e}")