"""Отчёты с фильтром периода и экспортом в PDF."""

from datetime import datetime, timedelta
from decimal import Decimal

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import func, select

from src.data.database import get_session
from src.data.orm_models import BookingORM, HallORM
from src.ui.widgets.common import build_topbar, make_button, make_table


class ReportsView(QWidget):
    """Экран «Отчёты» с фильтром периода и экспортом в PDF."""

    def __init__(self, main):
        super().__init__()
        self.main = main
        self.period = "month"
        self.sel_year = datetime.now().year
        self.sel_month = datetime.now().month
        self.sel_day = datetime.now().day
        self.sel_quarter = ((datetime.now().month - 1) // 3) + 1
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        root.addLayout(build_topbar(self.main, "Отчёты"))

        # ---------- Фильтр периода ----------
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("Период:"))

        self.period_buttons = {}
        for key, label in (
            ("day", "День"),
            ("month", "Месяц"),
            ("quarter", "Квартал"),
            ("year", "Год"),
        ):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, k=key: self._set_period(k))
            self.period_buttons[key] = btn
            filter_row.addWidget(btn)

        filter_row.addStretch()
        root.addLayout(filter_row)
        self._update_period_styles()

        # ---------- KPI ----------
        self.kpi = QLabel()
        self.kpi.setObjectName("subtitle")
        root.addWidget(self.kpi)

        root.addWidget(QLabel("Выручка по залам:"))

        self.table = make_table(["Зал", "Выручка"])
        root.addWidget(self.table, stretch=1)

        root.addWidget(QLabel("Статусы броней:"))

        self.status_table = make_table(["Статус", "Количество", "Доля"])
        root.addWidget(self.status_table, stretch=1)

        # ---------- Кнопки ----------
        btns = QHBoxLayout()
        btns.addWidget(make_button("Обновить", self.refresh, accent=True))
        btns.addWidget(make_button("Сохранить в PDF", self._export_pdf))
        btns.addStretch()
        root.addLayout(btns)

    # ---------- Период ----------

    def _set_period(self, key):
        """Переключает период с диалогом выбора даты."""
        self.period = key

        if key == "day":
            if not self._select_day():
                return
        elif key == "month":
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

    def _select_day(self):
        """Диалог выбора дня."""
        days = [str(d) for d in range(1, 32)]
        months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        years = [str(y) for y in range(datetime.now().year - 3, datetime.now().year + 2)]

        dlg = QDialog(self)
        dlg.setWindowTitle("Выбор дня")
        dlg.setMinimumWidth(280)
        form = QFormLayout(dlg)

        day_combo = QComboBox()
        day_combo.addItems(days)
        day_combo.setCurrentText(str(self.sel_day))

        month_combo = QComboBox()
        month_combo.addItems(months)
        month_combo.setCurrentIndex(self.sel_month - 1)

        year_combo = QComboBox()
        year_combo.addItems(years)
        year_combo.setCurrentText(str(self.sel_year))

        form.addRow("День:", day_combo)
        form.addRow("Месяц:", month_combo)
        form.addRow("Год:", year_combo)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)

        if dlg.exec_() != QDialog.Accepted:
            return False
        self.sel_day = int(day_combo.currentText())
        self.sel_month = month_combo.currentIndex() + 1
        self.sel_year = int(year_combo.currentText())
        return True

    def _select_month(self):
        """Диалог выбора месяца и года."""
        months = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                  "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
        years = [str(y) for y in range(datetime.now().year - 3, datetime.now().year + 2)]

        dlg = QDialog(self)
        dlg.setWindowTitle("Выбор месяца")
        dlg.setMinimumWidth(280)
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

    def _select_quarter(self):
        """Диалог выбора квартала и года."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Выбор квартала")
        dlg.setMinimumWidth(280)
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

    def _select_year(self):
        """Диалог выбора года."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Выбор года")
        dlg.setMinimumWidth(280)
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
        """Обновляет текст и стиль кнопок периода."""
        labels = {
            "day": f"{self.sel_day:02d}.{self.sel_month:02d}.{self.sel_year}",
            "month": f"{self.sel_month:02d}.{self.sel_year}",
            "quarter": f"{self.sel_quarter} кв. {self.sel_year}",
            "year": str(self.sel_year),
        }
        for k, btn in self.period_buttons.items():
            btn.setText(labels[k])
            if k == self.period:
                btn.setStyleSheet(
                    "QPushButton { background-color:#6F8E9E; color:white; "
                    "border:1px solid #5E7C8C; border-radius:6px; "
                    "padding:8px 16px; font-size:10pt; }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background-color:#FDF6E3; color:#2B2B2B; "
                    "border:1px solid #C8D4DA; border-radius:6px; "
                    "padding:8px 16px; font-size:10pt; }"
                    "QPushButton:hover { background-color:#E8D9B8; }"
                )

    def _period_range(self):
        """Возвращает (start, end) — границы выбранного периода."""
        if self.period == "day":
            start = datetime(self.sel_year, self.sel_month, self.sel_day, 0, 0, 0)
            end = start.replace(hour=23, minute=59, second=59)
        elif self.period == "month":
            start = datetime(self.sel_year, self.sel_month, 1, 0, 0, 0)
            if self.sel_month == 12:
                end = datetime(self.sel_year, 12, 31, 23, 59, 59)
            else:
                end = datetime(self.sel_year, self.sel_month + 1, 1) - timedelta(seconds=1)
        elif self.period == "quarter":
            q_month = (self.sel_quarter - 1) * 3 + 1
            start = datetime(self.sel_year, q_month, 1, 0, 0, 0)
            end_month = q_month + 2
            if end_month == 12:
                end = datetime(self.sel_year, 12, 31, 23, 59, 59)
            else:
                end = datetime(self.sel_year, end_month + 1, 1) - timedelta(seconds=1)
        else:  # year
            start = datetime(self.sel_year, 1, 1, 0, 0, 0)
            end = datetime(self.sel_year, 12, 31, 23, 59, 59)
        return start, end

    def _period_label(self):
        """Возвращает читаемое название периода."""
        labels = {
            "day": f"День: {self.sel_day:02d}.{self.sel_month:02d}.{self.sel_year}",
            "month": f"Месяц: {self.sel_month:02d}.{self.sel_year}",
            "quarter": f"Квартал: {self.sel_quarter} кв. {self.sel_year}",
            "year": f"Год: {self.sel_year}",
        }
        return labels[self.period]

    def _get_report_data(self):
        """Возвращает (total, count, rows) за выбранный период."""
        start, end = self._period_range()
        with get_session() as s:
            total = s.scalar(
                select(func.coalesce(func.sum(BookingORM.total_price), 0)).where(
                    BookingORM.start_datetime >= start,
                    BookingORM.start_datetime <= end,
                )
            ) or 0
            count = s.scalar(
                select(func.count(BookingORM.booking_id)).where(
                    BookingORM.start_datetime >= start,
                    BookingORM.start_datetime <= end,
                )
            ) or 0
            rows = s.execute(
                select(HallORM.name, func.coalesce(func.sum(BookingORM.total_price), 0))
                .join(BookingORM, BookingORM.hall_id == HallORM.hall_id)
                .where(
                    BookingORM.start_datetime >= start,
                    BookingORM.start_datetime <= end,
                )
                .group_by(HallORM.name)
            ).all()
        return Decimal(total), int(count), [(n, Decimal(a)) for n, a in rows]

    def _get_status_stats(self):
        """
        Возвращает список кортежей (название статуса, количество, процент)
        за выбранный период.
        """
        from src.data.orm_models import StatusORM

        start, end = self._period_range()

        with get_session() as s:
            # Все статусы
            statuses = list(s.scalars(select(StatusORM)).all())

            # Общее количество броней за период
            total_count = s.scalar(
                select(func.count(BookingORM.booking_id)).where(
                    BookingORM.start_datetime >= start,
                    BookingORM.start_datetime <= end,
                )
            ) or 0

            # Количество по каждому статусу
            stats = []
            for st in statuses:
                cnt = s.scalar(
                    select(func.count(BookingORM.booking_id)).where(
                        BookingORM.start_datetime >= start,
                        BookingORM.start_datetime <= end,
                        BookingORM.status_id == st.status_id,
                    )
                ) or 0

                percent = (cnt / total_count * 100) if total_count > 0 else 0
                stats.append((st.name, int(cnt), float(percent)))

        return stats, int(total_count)

    # ---------- Обновление ----------

    def refresh(self):
        """Обновляет KPI и таблицы с учётом выбранного периода."""
        total, count, rows = self._get_report_data()
        self.kpi.setText(
            f"{self._period_label()}  |  "
            f"Выручка: <b>{total:.2f} ₽</b>  |  "
            f"Броней: <b>{count}</b>"
        )

        # Таблица «Выручка по залам»
        self.table.setRowCount(len(rows))
        for i, (name, amount) in enumerate(rows):
            self.table.setItem(i, 0, QTableWidgetItem(name))
            self.table.setItem(i, 1, QTableWidgetItem(f"{amount:.2f} ₽"))

        # Таблица «Статусы броней»
        if hasattr(self, "status_table"):
            stats, total_count = self._get_status_stats()
            self.status_table.setRowCount(len(stats))
            for i, (name, cnt, percent) in enumerate(stats):
                self.status_table.setItem(i, 0, QTableWidgetItem(name))
                self.status_table.setItem(i, 1, QTableWidgetItem(str(cnt)))
                self.status_table.setItem(
                    i, 2, QTableWidgetItem(f"{percent:.1f} %")
                )
    # ---------- Экспорт в PDF ----------

    def _export_pdf(self):
        """Экспортирует отчёт за выбранный период в PDF."""
        import os
        from datetime import datetime as _dt
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from PyQt5.QtWidgets import QFileDialog

        start, end = self._period_range()
        total, count, rows = self._get_report_data()
        period_label = self._period_label()

        default_name = f"report_{self.period}_{_dt.now().strftime('%Y%m%d_%H%M')}.pdf"
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить отчёт", default_name, "PDF (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        # Автопоиск шрифта с поддержкой кириллицы
        font_name = "Helvetica"
        try:
            for candidate in (
                "C:/Windows/Fonts/DejaVuSans.ttf",
                "C:/Windows/Fonts/arial.ttf",
                "C:/Windows/Fonts/times.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ):
                if os.path.exists(candidate):
                    pdfmetrics.registerFont(TTFont("CustomFont", candidate))
                    font_name = "CustomFont"
                    break
        except Exception:
            pass

        c = canvas.Canvas(path, pagesize=A4)
        width, height = A4
        y = height - 60

        c.setFont(font_name, 18)
        c.drawString(50, y, "FS.Booking — Отчёт")
        y -= 30

        c.setFont(font_name, 10)
        c.drawString(50, y, f"{period_label}")
        y -= 18
        c.drawString(50, y, f"Период: {start.strftime('%d.%m.%Y')} — {end.strftime('%d.%m.%Y')}")
        y -= 18
        c.drawString(50, y, f"Дата формирования: {_dt.now().strftime('%d.%m.%Y %H:%M')}")
        y -= 30

        c.setFont(font_name, 13)
        c.drawString(50, y, "Ключевые показатели:")
        y -= 22

        c.setFont(font_name, 11)
        c.drawString(70, y, f"Общая выручка: {total:.2f} руб.")
        y -= 18
        c.drawString(70, y, f"Количество броней: {count}")
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

        for name, amount in rows:
            c.drawString(70, y, str(name))
            c.drawString(300, y, f"{amount:.2f} руб.")
            y -= 18
            if y < 60:
                c.showPage()
                c.setFont(font_name, 11)
                y = height - 60

        # --- Статусы броней в процентах ---
        stats, total_count = self._get_status_stats()

        y -= 20
        if y < 100:
            c.showPage()
            y = height - 60

        c.setFont(font_name, 13)
        c.drawString(50, y, "Статусы броней:")
        y -= 22

        c.setFont(font_name, 11)
        c.drawString(70, y, "Статус")
        c.drawString(300, y, "Количество")
        c.drawString(430, y, "Доля")
        y -= 6
        c.line(70, y, 500, y)
        y -= 16

        c.setFont(font_name, 11)
        for name, cnt, percent in stats:
            c.drawString(70, y, str(name))
            c.drawString(300, y, str(cnt))
            c.drawString(430, y, f"{percent:.1f} %")
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
        self.refresh()
        super().showEvent(event)