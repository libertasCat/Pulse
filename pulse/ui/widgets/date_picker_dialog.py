"""自定义日期选择对话框 —— 纯 QPainter 月历（不依赖 QCalendarWidget）."""

import calendar
from datetime import date
from typing import Callable, Optional

from PyQt6.QtCore import QPointF, QRectF, Qt  # type: ignore
from PyQt6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPainterPath, QPen  # type: ignore
from PyQt6.QtWidgets import (  # type: ignore
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)


class _MonthGrid(QWidget):
    """QPainter 绘制的月历网格（用于选日期）. """

    def __init__(self, initial: date, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFixedSize(320, 260)
        self._year = initial.year
        self._month = initial.month
        self._selected = initial
        self._hover_day = 0
        self.on_select: Optional[Callable[[date], None]] = None

    # ── 布局 ──
    def _layout(self):
        _, self._last_day = calendar.monthrange(self._year, self._month)
        self._first_wd = date(self._year, self._month, 1).weekday()
        # 防止未布局时 width/height 为 0 导致除零
        self._cw = max(self.width(), 7) / 7
        self._ch = max(self.height() - 26, 6) / 6

    def _day_at(self, x: float, y: float) -> int:
        if y < 26:
            return 0
        col = int(x / self._cw)
        row = int((y - 26) / self._ch)
        day = row * 7 + col + 1 - self._first_wd
        return day if 1 <= day <= self._last_day else 0

    # ── 绘制 ──
    def paintEvent(self, event):
        self._layout()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(0, 0, self.width(), self.height(), QColor("#25253a"))

        # 星期头
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        for col, name in enumerate(["一", "二", "三", "四", "五", "六", "日"]):
            painter.setPen(QColor("#f44336" if col >= 5 else "#808098"))
            painter.drawText(QRectF(col * self._cw, 0, self._cw, 26),
                             Qt.AlignmentFlag.AlignCenter, name)

        painter.setPen(QPen(QColor("#3a3a50"), 1))
        painter.drawLine(0, 26, self.width(), 26)

        # 日期格子
        today = date.today()
        for r in range(6):
            for c in range(7):
                day_num = r * 7 + c + 1 - self._first_wd
                x, y = c * self._cw, 26 + r * self._ch
                in_month = 1 <= day_num <= self._last_day

                painter.setPen(QPen(QColor("#3a3a50"), 1))
                painter.drawRect(QRectF(x, y, self._cw, self._ch))
                if not in_month:
                    continue

                is_selected = (self._year == self._selected.year and
                               self._month == self._selected.month and
                               day_num == self._selected.day)
                is_today = (self._year == today.year and
                            self._month == today.month and day_num == today.day)
                is_hover = (day_num == self._hover_day)

                # 背景
                if is_selected:
                    painter.fillRect(QRectF(x + 2, y + 2, self._cw - 4, self._ch - 4), QColor("#7c5cfc"))
                elif is_hover:
                    painter.fillRect(QRectF(x + 2, y + 2, self._cw - 4, self._ch - 4), QColor("#3a3a5a"))

                # 文字
                if is_selected:
                    painter.setPen(QColor("#ffffff"))
                elif is_today:
                    painter.setPen(QColor("#9b7cff"))
                else:
                    painter.setPen(QColor("#e0e0e8"))
                painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold if is_today else QFont.Weight.Medium))
                painter.drawText(QRectF(x, y, self._cw, self._ch), Qt.AlignmentFlag.AlignCenter, str(day_num))

        painter.end()

    # ── 鼠标 ──
    def mouseMoveEvent(self, event: QMouseEvent):
        day = self._day_at(int(event.position().x()), int(event.position().y()))
        if day != self._hover_day:
            self._hover_day = day
            self.update()

    def mousePressEvent(self, event: QMouseEvent):
        day = self._day_at(int(event.position().x()), int(event.position().y()))
        if day > 0:
            self._selected = date(self._year, self._month, day)
            self.update()
            if self.on_select:
                self.on_select(self._selected)

    def leaveEvent(self, event):
        self._hover_day = 0
        self.update()


class DatePickerDialog(QDialog):
    """日期选择对话框 —— 显示月份导航 + QPainter 月历."""

    def __init__(self, initial: date, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择日期")
        self.setModal(True)
        self.setFixedSize(340, 340)
        self._result_date: Optional[date] = None

        lo = QVBoxLayout(self)
        lo.setContentsMargins(10, 10, 10, 10)
        lo.setSpacing(6)

        # ── 月份导航 ──
        nav = QHBoxLayout()
        prev_btn = QPushButton("◀")
        prev_btn.setFixedSize(28, 28)
        prev_btn.setStyleSheet("QPushButton { border: none; border-radius: 4px; color: #a0a0b8; }"
                               "QPushButton:hover { background: #2a2a44; }")
        prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prev_btn.clicked.connect(self._prev_month)

        self._nav_label = QLabel()
        self._nav_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._nav_label.setStyleSheet("color: #e0e0e8; font-size: 13px; font-weight: 600;")

        next_btn = QPushButton("▶")
        next_btn.setFixedSize(28, 28)
        next_btn.setStyleSheet("QPushButton { border: none; border-radius: 4px; color: #a0a0b8; }"
                               "QPushButton:hover { background: #2a2a44; }")
        next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        next_btn.clicked.connect(self._next_month)

        nav.addWidget(prev_btn)
        nav.addWidget(self._nav_label, stretch=1)
        nav.addWidget(next_btn)
        lo.addLayout(nav)

        # ── 月历 ──
        self._grid = _MonthGrid(initial)
        self._grid.on_select = self._on_day_selected
        lo.addWidget(self._grid, alignment=Qt.AlignmentFlag.AlignCenter)

        # ── 今天按钮 ──
        today_btn = QPushButton("今天")
        today_btn.setStyleSheet(
            "QPushButton { background: #7c5cfc; border: none; border-radius: 4px; "
            "padding: 6px; color: #fff; font-weight: 600; font-size: 12px; }"
            "QPushButton:hover { background: #6a4acc; }"
        )
        today_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        today_btn.clicked.connect(lambda: self._on_day_selected(date.today()))
        lo.addWidget(today_btn)

        self._update_label()

    def _update_label(self):
        names = ["", "一月", "二月", "三月", "四月", "五月", "六月",
                 "七月", "八月", "九月", "十月", "十一月", "十二月"]
        self._nav_label.setText(f"{names[self._grid._month]} {self._grid._year}")

    def _prev_month(self):
        if self._grid._month == 1:
            self._grid._year -= 1
            self._grid._month = 12
        else:
            self._grid._month -= 1
        self._update_label()
        self._grid.update()

    def _next_month(self):
        if self._grid._month == 12:
            self._grid._year += 1
            self._grid._month = 1
        else:
            self._grid._month += 1
        self._update_label()
        self._grid.update()

    def _on_day_selected(self, d: date):
        self._result_date = d
        self.accept()

    def get_selected(self) -> Optional[date]:
        return self._result_date
