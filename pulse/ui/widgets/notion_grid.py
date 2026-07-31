"""Notion 风格月历网格 —— 纯 QPainter，错行排列，简洁风格."""

import calendar
from datetime import date
from typing import Callable, Optional

from PyQt6.QtCore import QRectF, Qt, QVariantAnimation  # type: ignore
from PyQt6.QtGui import (  # type: ignore
    QColor, QCursor, QFont, QMouseEvent, QPainter, QPainterPath, QPen,
)
from PyQt6.QtWidgets import QWidget  # type: ignore


class NotionGrid(QWidget):
    """QPainter 月历网格：错行任务条 + 简洁边框风格 + 拖拽延长."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._year = date.today().year
        self._month = date.today().month
        self._today = date.today()
        self._tasks: list = []
        self._hover_day = 0
        self._hover_task_id: Optional[int] = None
        self._drag_side_task_id: Optional[int] = None
        self._drag_target_day: Optional[int] = None

        # + 按钮 hover 动画
        self._plus_anim = QVariantAnimation(self)
        self._plus_anim.setDuration(150)
        self._plus_anim.setStartValue(0.0)
        self._plus_anim.setEndValue(1.0)
        self._plus_anim.valueChanged.connect(self._on_plus_anim)
        self._plus_progress = 0.0

        self.on_task_click: Optional[Callable[[int], None]] = None
        self.on_cell_add: Optional[Callable[[int, int, int], None]] = None
        self.on_task_drag: Optional[Callable[[int, int], None]] = None

    # ── 数据 ────────────────────────────────────────────

    def set_data(self, year: int, month: int, tasks: list):
        self._year = year
        self._month = month
        self._tasks = []
        for i, row in enumerate(tasks):
            task = row[0]
            end_day = task.end_date.day if task.end_date else task.date.day
            self._tasks.append((task.id, task.date.day, end_day, task.title))
        self.update()

    # ── 布局 ────────────────────────────────────────────

    def _layout(self):
        _, self._last_day = calendar.monthrange(self._year, self._month)
        self._first_wd = date(self._year, self._month, 1).weekday()
        self._header_h = 30
        w = max(self.width(), 1)
        self._cell_w = w / 7
        self._cell_h = max(self.height() - self._header_h, 1) / 6

    def _day_at(self, x: float, y: float) -> int:
        if y < self._header_h:
            return 0
        col = int(x / self._cell_w)
        row = int((y - self._header_h) / self._cell_h)
        day = row * 7 + col + 1 - self._first_wd
        return day if 1 <= day <= self._last_day else 0

    def _get_stack(self) -> dict[int, int]:
        """计算每个任务的堆叠行 (task_id → row_index)."""
        stack: dict[int, list[int]] = {}
        rows: dict[int, int] = {}
        for tid, sd, ed, title in sorted(self._tasks, key=lambda t: (t[1], t[2])):
            assigned = None
            for row_idx in range(10):
                if not any(d in stack and row_idx in stack[d] for d in range(sd, ed + 1) if 1 <= d <= self._last_day):
                    assigned = row_idx
                    break
            if assigned is None:
                assigned = 0
            rows[tid] = assigned
            for d in range(sd, ed + 1):
                if 1 <= d <= self._last_day:
                    stack.setdefault(d, []).append(assigned)
        return rows

    # ── 绘制 ────────────────────────────────────────────

    def paintEvent(self, event):
        self._layout()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, cw, ch = self.width(), self._cell_w, self._cell_h

        # 背景
        painter.fillRect(0, 0, w, self.height(), QColor("#1a1a2e"))

        # 星期头
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        for col, name in enumerate(["一", "二", "三", "四", "五", "六", "日"]):
            painter.setPen(QColor("#f44336" if col >= 5 else "#808098"))
            painter.drawText(QRectF(col * cw, 0, cw, self._header_h), Qt.AlignmentFlag.AlignCenter, name)

        painter.setPen(QPen(QColor("#2a2a40"), 1))
        painter.drawLine(0, self._header_h, w, self._header_h)

        # ── 格子 + 日期 ──
        for r in range(6):
            for c in range(7):
                day_num = r * 7 + c + 1 - self._first_wd
                x, y = c * cw, self._header_h + r * ch
                in_month = 1 <= day_num <= self._last_day

                painter.setPen(QPen(QColor("#2a2a40"), 1))
                painter.drawRect(QRectF(x, y, cw, ch))
                if not in_month:
                    continue

                is_today = (self._year == self._today.year and
                            self._month == self._today.month and day_num == self._today.day)

                # ── 右上角：日期 ──
                if is_today:
                    path = QPainterPath()
                    path.addEllipse(x + cw - 32, y + 4, 28, 28)
                    painter.fillPath(path, QColor("#7c5cfc"))
                    painter.setPen(QColor("#ffffff"))
                else:
                    painter.setPen(QColor("#ffffff"))
                painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold if is_today else QFont.Weight.Medium))
                painter.drawText(QRectF(x + cw - 40, y + 4, 36, 28), Qt.AlignmentFlag.AlignCenter, str(day_num))

                # ── 左上角：圆角矩形 + 按钮（Notion 风格） ──
                if in_month:
                    is_hover_btn = (day_num == self._hover_day)
                    t = self._plus_progress if is_hover_btn else 0.0
                    bg_r = int(0x2A + (0x7C - 0x2A) * t)
                    bg_g = int(0x2A + (0x5C - 0x2A) * t)
                    bg_b = int(0x44 + (0xFC - 0x44) * t)
                    fg_r = int(0x80 + (0xFF - 0x80) * t)
                    fg_g = int(0x80 + (0xFF - 0x80) * t)
                    fg_b = int(0x98 + (0xFF - 0x98) * t)
                    # 圆角矩形（20x18，位于左上角）
                    rect = QRectF(x + 4, y + 7, 20, 18)
                    path2 = QPainterPath()
                    path2.addRoundedRect(rect, 4, 4)
                    painter.fillPath(path2, QColor(bg_r, bg_g, bg_b))
                    painter.setPen(QColor(fg_r, fg_g, fg_b))
                    painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
                    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "+")

        # ── 任务条（单次绘制，错行堆叠，简洁边框） ──
        task_rows = self._get_stack()

        painter.setFont(QFont("Segoe UI", 10))
        for tid, sd, ed, title in self._tasks:
            s_col = (sd + self._first_wd - 1) % 7
            s_row = (sd + self._first_wd - 1) // 7
            e_day = min(ed, self._last_day)
            e_col = (e_day + self._first_wd - 1) % 7
            e_row = (e_day + self._first_wd - 1) // 7
            if s_row != e_row:
                e_col = 6

            stack_row = task_rows.get(tid, 0)
            bx = s_col * cw + 2
            by = self._header_h + s_row * ch + 34 + stack_row * 22
            bw = (e_col - s_col + 1) * cw - 4
            bh = 19

            is_hover = (tid == self._hover_task_id)

            # 背景 + 边框
            painter.setPen(QPen(QColor("#7c5cfc" if is_hover else "#3a3a50"), 1))
            painter.setBrush(QColor("#25253a"))
            path = QPainterPath()
            path.addRoundedRect(bx, by, bw, bh, 3, 3)
            painter.drawPath(path)

            # 左侧小竖条
            painter.setPen(Qt.PenStyle.NoPen)
            painter.fillRect(QRectF(bx + 1, by + 2, 3, bh - 4), QColor("#7c5cfc"))

            # 文字
            painter.setPen(QColor("#e0e0e8"))
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold if is_hover else QFont.Weight.Normal))
            text = title[:int(bw / 7.5)] + ".." if len(title) > int(bw / 7.5) else title
            painter.drawText(QRectF(bx + 8, by, bw - 14, bh),
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

            # 拖拽手柄
            if is_hover and bw > 40:
                painter.fillRect(QRectF(bx + bw - 10, by + 2, 6, bh - 4), QColor(255, 255, 255, 60))

        painter.end()

    def _cell_pos(self, day_num: int):
        """返回 (row, col) 和 (x, y)."""
        idx = day_num + self._first_wd - 1
        row, col = idx // 7, idx % 7
        return row, col, (col * self._cell_w, self._header_h + row * self._cell_h)

    # ── 鼠标 ────────────────────────────────────────────

    def _on_plus_anim(self, value: float):
        self._plus_progress = float(value)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        x, y = int(event.position().x()), int(event.position().y())
        new_day = self._day_at(x, y)
        if new_day != self._hover_day:
            # 开始 hover 动画
            self._plus_anim.stop()
            self._plus_progress = 1.0 if new_day > 0 else 0.0
            if new_day > 0:
                self._plus_anim.setStartValue(0.0)
                self._plus_anim.setEndValue(1.0)
                self._plus_anim.start()
            else:
                self._plus_anim.setStartValue(1.0)
                self._plus_anim.setEndValue(0.0)
                self._plus_anim.start()
        self._hover_day = new_day

        if self._drag_side_task_id is not None:
            nd = self._hover_day
            if nd > 0 and nd != self._drag_target_day:
                self._drag_target_day = nd
                for i, (tid, sd, ed, title) in enumerate(self._tasks):
                    if tid == self._drag_side_task_id:
                        self._tasks[i] = (tid, sd, max(sd, nd), title)
                        break
                self.update()
            return

        # hover 任务条
        old_ht = self._hover_task_id
        self._hover_task_id = None
        if self._hover_day > 0:
            task_rows = self._get_stack()
            _, _, (cx, cy) = self._cell_pos(self._hover_day)
            for tid, sd, ed, title in self._tasks:
                if not (sd <= self._hover_day <= ed):
                    continue
                sr = task_rows.get(tid, 0)
                ty = cy + 34 + sr * 22
                if ty <= y < ty + 20:
                    self._hover_task_id = tid
                    # 检测右边缘
                    e_day = min(ed, self._last_day)
                    e_col = (e_day + self._first_wd - 1) % 7
                    ecx = e_col * self._cell_w
                    bar_right = ecx + self._cell_w
                    if abs(x - bar_right) < 12:
                        self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
                    else:
                        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                    break
            if not self._hover_task_id:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

        if old_ht != self._hover_task_id:
            self.update()

    def mousePressEvent(self, event: QMouseEvent):
        x, y = int(event.position().x()), int(event.position().y())
        day = self._day_at(x, y)
        if day <= 0:
            return

        # + 按钮（左上角圆角矩形）
        col = int(x / self._cell_w)
        row = int((y - self._header_h) / self._cell_h) if y >= self._header_h else -1
        cx = col * self._cell_w
        cy = self._header_h + row * self._cell_h
        if (cx + 4 <= x <= cx + 24 and
                cy + 7 <= y <= cy + 25 and self._hover_day == day):
            if self.on_cell_add:
                self.on_cell_add(self._year, self._month, day)
            return

        # 任务点击 + 拖拽
        task_rows = self._get_stack()
        _, _, (cx, cy) = self._cell_pos(day)
        for tid, sd, ed, title in self._tasks:
            if not (sd <= day <= ed):
                continue
            sr = task_rows.get(tid, 0)
            ty = cy + 34 + sr * 22
            if ty <= y < ty + 20:
                e_day = min(ed, self._last_day)
                e_col = (e_day + self._first_wd - 1) % 7
                ecx = e_col * self._cell_w
                bar_right = ecx + self._cell_w
                if abs(x - bar_right) < 12:
                    self._drag_side_task_id = tid
                    self._drag_target_day = e_day
                    return
                if self.on_task_click:
                    self.on_task_click(tid)
                return

    def mouseReleaseEvent(self, event):
        if self._drag_side_task_id is not None and self._drag_target_day is not None:
            if self.on_task_drag:
                self.on_task_drag(self._drag_side_task_id, self._drag_target_day)
            self._drag_side_task_id = None
            self._drag_target_day = None
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        x = int(event.position().x())
        y = int(event.position().y())
        day = self._day_at(x, y)
        if not (day > 0 and self.on_cell_add):
            return

        # 跳过 + 按钮区域（防止 press + double-click 双重触发）
        col = int(x / self._cell_w)
        row = int((y - self._header_h) / self._cell_h) if y >= self._header_h else -1
        cx2 = col * self._cell_w
        cy2 = self._header_h + row * self._cell_h
        if (cx2 + 4 <= x <= cx2 + 24 and
                cy2 + 7 <= y <= cy2 + 25):
            return

        # 检查是否点击在任务条上
        _, _, (cx, cy) = self._cell_pos(day)
        task_rows = self._get_stack()
        on_task = False
        for tid, sd, ed, title in self._tasks:
            if not (sd <= day <= ed):
                continue
            sr = task_rows.get(tid, 0)
            ty = cy + 34 + sr * 22
            if ty <= y < ty + 20:
                on_task = True
                break
        if not on_task:
            self.on_cell_add(self._year, self._month, day)

    def leaveEvent(self, event):
        self._hover_day = 0
        self._hover_task_id = None
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        # 淡出动画
        if self._plus_progress > 0:
            self._plus_anim.stop()
            self._plus_anim.setStartValue(self._plus_progress)
            self._plus_anim.setEndValue(0.0)
            self._plus_anim.start()
        else:
            self.update()

    def minimumSizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(560, 400)
