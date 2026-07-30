"""可复用的图表控件 —— QPainter 绘制，无外部依赖."""

import calendar
from datetime import date
from typing import Optional

from PyQt6.QtCore import Qt, QRectF, QSize, QRect
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QWidget


class HorizontalBarChart(QWidget):
    """水平柱状图 —— 显示 Top N 应用使用时长，可选图标."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[tuple[str, int, str, Optional[QIcon]]] = []  # (label, value, color_hex, icon)
        self._max_value = 1

    def set_data(self, data: list[tuple[str, int, str, Optional[QIcon]]]) -> None:
        self._data = data
        vals = [v for _, v, _, _ in data]
        self._max_value = max(vals, default=1) or 1
        self.update()

    def paintEvent(self, event):
        if not self._data:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        margin = 8
        bar_h = 28
        gap = 6
        icon_size = 20
        icon_margin = 4
        label_w = 130
        value_w = 72
        bar_start_x = margin + icon_size + icon_margin + label_w + 8
        bar_max_w = w - margin - bar_start_x - value_w - 4

        y = margin
        for label, value, color_hex, icon in self._data:
            # ── icon ──
            if icon:
                ix = margin + icon_margin
                iy = y + (bar_h - icon_size) // 2
                pm = icon.pixmap(icon_size, icon_size)
                painter.drawPixmap(ix, iy, pm)

            # ── label ──
            painter.setPen(QColor("#c0c0d0"))
            font = QFont("Segoe UI", 11)
            painter.setFont(font)
            elided = label[:20] + ".." if len(label) > 20 else label
            label_x = margin + icon_size + icon_margin + 2
            painter.drawText(QRectF(label_x, y, label_w, bar_h),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)

            # ── bar ──
            fraction = value / self._max_value
            bar_w = max(4, int(bar_max_w * fraction))
            bar_color = QColor(color_hex)
            bar_rect = QRectF(bar_start_x, y + 2, bar_w, bar_h - 4)
            path = QPainterPath()
            path.addRoundedRect(bar_rect, 4, 4)
            painter.fillPath(path, bar_color)

            # ── value on bar ──
            h = value // 3600
            m = (value % 3600) // 60
            time_str = f"{h}h {m:02d}m" if h else f"{m:02d}m"
            if bar_w > 60:
                painter.setPen(QColor("#ffffff"))
                painter.drawText(QRectF(bar_start_x + 4, y, bar_w - 8, bar_h),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, time_str)

            # ── right value ──
            painter.setPen(QColor("#808098"))
            painter.drawText(QRectF(w - margin - value_w, y, value_w, bar_h),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, time_str)

            y += bar_h + gap

        painter.end()

    def minimumSizeHint(self):
        return QSize(400, 200)


class PieChart(QWidget):
    """饼状图 —— 显示分类占比."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[tuple[str, int, str]] = []  # (label, value, color_hex)
        self._total = 0

    def set_data(self, data: list[tuple[str, int, str]]) -> None:
        self._data = data
        self._total = max(sum(v for _, v, _ in data), 1)
        self.update()

    def paintEvent(self, event):
        if not self._data:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height())
        center_x = side // 2
        center_y = side // 2
        radius = side // 2 - 24

        # ── 绘制饼图 ──
        start_angle = 90 * 16  # start from top
        for label, value, color_hex in self._data:
            if value <= 0:
                continue
            span = int(360 * 16 * value / self._total)
            painter.setBrush(QColor(color_hex))
            painter.setPen(QPen(QColor("#1a1a2e"), 2))
            painter.drawPie(QRectF(center_x - radius, center_y - radius,
                                   radius * 2, radius * 2),
                            start_angle, span)
            start_angle += span

        # ── 图例 ──
        legend_x = side + 20
        legend_y = 20
        painter.setFont(QFont("Segoe UI", 10))
        for label, value, color_hex in self._data:
            pct = value / self._total * 100
            # color dot
            painter.setBrush(QColor(color_hex))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(legend_x, legend_y, 12, 12, 2, 2)
            # text
            painter.setPen(QColor("#c0c0d0"))
            text = f"{label}  {pct:.0f}%  ({value // 60}m)"
            painter.drawText(QRectF(legend_x + 20, legend_y, 140, 14),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
            legend_y += 24

        painter.end()

    def minimumSizeHint(self):
        return QSize(300, 200)


class HourlyTimeline(QWidget):
    """24 小时时间线 —— 每小时活跃度柱状图."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[int] = [0] * 24  # 每小时秒数
        self._max_val = 1

    def set_data(self, hourly_seconds: list[int]) -> None:
        self._data = hourly_seconds
        self._max_val = max(hourly_seconds, default=1)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        margin_left = 36
        margin_right = 12
        margin_top = 12
        margin_bottom = 28
        chart_w = w - margin_left - margin_right
        chart_h = h - margin_top - margin_bottom
        bar_w = chart_w / 24 - 2

        for hour in range(24):
            x = margin_left + hour * (chart_w / 24) + 1
            frac = self._data[hour] / self._max_val
            bar_h = max(2, int(chart_h * frac))
            y = margin_top + chart_h - bar_h

            # 颜色：按活跃度渐变
            intensity = min(1.0, frac * 1.5)
            r = int(124 * intensity)
            g = int(92 * (0.5 + 0.5 * intensity))
            b = int(252 * (0.3 + 0.7 * intensity))
            color = QColor(min(255, r), min(255, g), min(255, b))

            path = QPainterPath()
            path.addRoundedRect(QRectF(x, y, bar_w, bar_h), 2, 2)
            painter.fillPath(path, color)

            # 小时标签（每 3 小时）
            if hour % 3 == 0:
                painter.setPen(QColor("#808098"))
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(QRectF(x - 8, margin_top + chart_h + 4, 28, 20),
                                 Qt.AlignmentFlag.AlignCenter, f"{hour:02d}")

        painter.end()

    def minimumSizeHint(self):
        return QSize(400, 140)


class HeatmapCalendar(QWidget):
    """热力日历图 —— 类似 GitHub 贡献图，展示每日使用量."""

    COLORS = ["#2d2d45", "#4a3a7a", "#6a4acc", "#7c5cfc", "#9b7cff"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._year: int = date.today().year
        self._month: int = date.today().month
        self._data: dict[int, int] = {}  # day -> total_seconds
        self._max_val = 1

    def set_data(self, year: int, month: int, daily_totals: list[dict]) -> None:
        self._year = year
        self._month = month
        self._data = {}
        for entry in daily_totals:
            d = entry["date"]
            if isinstance(d, date):
                self._data[d.day] = entry["total_seconds"]
            else:
                try:
                    self._data[entry["date"].day] = entry["total_seconds"]
                except Exception:
                    pass
        self._max_val = max(self._data.values(), default=1)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        _, last_day = calendar.monthrange(self._year, self._month)
        first_weekday = date(self._year, self._month, 1).weekday()  # Mon=0

        cell_size = 22
        gap = 4
        margin_x = 20
        margin_y = 40
        cols = 7

        # ── 标题 ──
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        month_name = ["", "一月", "二月", "三月", "四月", "五月", "六月",
                       "七月", "八月", "九月", "十月", "十一月", "十二月"]
        painter.drawText(QRectF(margin_x, 0, 200, 30),
                         Qt.AlignmentFlag.AlignLeft, f"{self._year} {month_name[self._month]}")

        # ── 星期标题 ──
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#808098"))
        days = ["一", "二", "三", "四", "五", "六", "日"]
        for i, d in enumerate(days):
            x = margin_x + i * (cell_size + gap)
            painter.drawText(QRectF(x, 22, cell_size, 16),
                             Qt.AlignmentFlag.AlignCenter, d)

        # ── 格子 ──
        for day_num in range(1, last_day + 1):
            weekday = date(self._year, self._month, day_num).weekday()
            week_num = (day_num + first_weekday - 1) // 7
            col = weekday
            row = week_num

            x = margin_x + col * (cell_size + gap)
            y = margin_y + row * (cell_size + gap)

            secs = self._data.get(day_num, 0)
            if secs == 0:
                color_idx = 0
            else:
                frac = secs / max(self._max_val, 1)
                color_idx = min(4, int(frac * 4) + 1)

            painter.setBrush(QColor(self.COLORS[color_idx]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, y, cell_size, cell_size, 3, 3)

            # 日期数字
            if secs > 0:
                painter.setPen(QColor("#ffffff"))
            else:
                painter.setPen(QColor("#606080"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(QRectF(x, y, cell_size, cell_size),
                             Qt.AlignmentFlag.AlignCenter, str(day_num))

        # ── 图例 ──
        legend_y = margin_y + ((last_day + first_weekday) // 7 + 1) * (cell_size + gap) + 12
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor("#808098"))
        painter.drawText(QRectF(margin_x, legend_y, 60, 16),
                         Qt.AlignmentFlag.AlignLeft, "少")
        for i, c in enumerate(self.COLORS):
            x = margin_x + 30 + i * (cell_size + 2)
            painter.setBrush(QColor(c))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(x, legend_y, 14, 14, 2, 2)
        painter.setPen(QColor("#808098"))
        painter.drawText(QRectF(margin_x + 30 + 5 * (cell_size + 2), legend_y, 30, 16),
                         Qt.AlignmentFlag.AlignLeft, "多")

        painter.end()

    def minimumSizeHint(self):
        return QSize(280, 280)
