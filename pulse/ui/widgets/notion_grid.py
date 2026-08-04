"""Notion 风格月历网格 —— 纯 QPainter，可变行高，任务堆叠."""

import calendar
from datetime import date
from typing import Callable, Optional

from PyQt6.QtCore import QPointF, QRectF, Qt, QVariantAnimation  # type: ignore
from PyQt6.QtGui import (  # type: ignore
    QColor, QCursor, QFont, QMouseEvent, QPainter, QPainterPath, QPen,
)
from PyQt6.QtWidgets import QWidget  # type: ignore


class NotionGrid(QWidget):
    """QPainter 月历网格：错行任务条 + 可变行高 + 拖拽延长."""

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
        # 左边拖拽（移动开始日期）
        self._drag_left_task_id: Optional[int] = None
        self._drag_left_target_day: Optional[int] = None

        self._plus_anim = QVariantAnimation(self)
        self._plus_anim.setDuration(150)
        self._plus_anim.setStartValue(0.0)
        self._plus_anim.setEndValue(1.0)
        self._plus_anim.valueChanged.connect(self._on_plus_anim)
        self._plus_progress = 0.0

        self.on_task_click: Optional[Callable[[int], None]] = None
        self.on_cell_add: Optional[Callable[[int, int, int], None]] = None
        self.on_task_drag: Optional[Callable[[int, int], None]] = None          # 右拉：更新结束日期
        self.on_task_left_drag: Optional[Callable[[int, int], None]] = None     # 左拉：更新开始日期

    # ── 数据 ────────────────────────────────────────────

    def set_data(self, year: int, month: int, tasks: list):
        self._year = year
        self._month = month
        self._tasks = []
        for i, row in enumerate(tasks):
            task = row[0]
            end = task.end_date or task.date
            self._tasks.append((task.id, task.date, end, task.title))
        self.update()

    def _clamp(self, start: date, end: date) -> tuple[int, int]:
        """把任务的起止日期裁剪到当前月内的天数范围."""
        month_first = date(self._year, self._month, 1)
        month_last = date(self._year, self._month, self._last_day)
        if end < month_first or start > month_last:
            return 0, 0  # 与当月无交集
        s_day = start.day if start >= month_first else 1
        e_day = end.day if end <= month_last else self._last_day
        return s_day, e_day

    def _task_left_draggable(self, start: date) -> bool:
        """任务左边缘是否可拖拽（仅当开始日期在当月内）. """
        return start.year == self._year and start.month == self._month

    # ── 布局 ────────────────────────────────────────────

    def _layout(self):
        _, self._last_day = calendar.monthrange(self._year, self._month)
        self._first_wd = date(self._year, self._month, 1).weekday()
        self._header_h = 30
        w = max(self.width(), 1)
        self._cell_w = w / 7

        # 计算每行的最大任务堆叠数 → 可变行高
        task_rows = self._get_stack()
        max_stack_per_row: dict[int, int] = {}
        for tid, sd, ed, title in self._tasks:
            s_day, _ = self._clamp(sd, ed)
            if s_day <= 0:
                continue
            s_row = (s_day + self._first_wd - 1) // 7
            sr = task_rows.get(tid, 0)
            max_stack_per_row[s_row] = max(max_stack_per_row.get(s_row, 0), sr + 1)

        # 基础行高：日期头 34px + 任务条堆叠
        base = [max(60, 34 + max_stack_per_row.get(r, 0) * 22 + 4) for r in range(6)]

        # 按可用高度等比缩放（保底最小 50px）
        avail = max(self.height() - self._header_h, 1)
        total = sum(base)
        scale = avail / total if total > 0 else 1
        self._row_heights = [max(50, h * scale) for h in base]
        # 缩放后再归一化，避免总和超出
        total2 = sum(self._row_heights)
        if total2 > 0 and total2 != avail:
            self._row_heights = [h * avail / total2 for h in self._row_heights]

    def _row_y(self, row: int) -> float:
        """第 row 行的 y 坐标."""
        return self._header_h + sum(self._row_heights[:row])

    def _row_at_y(self, y: float) -> int:
        """根据 y 坐标找到所在行."""
        if y < self._header_h:
            return -1
        yy = y - self._header_h
        for i, h in enumerate(self._row_heights):
            if yy < h:
                return i
            yy -= h
        return 5

    def _day_at(self, x: float, y: float) -> int:
        if y < self._header_h:
            return 0
        col = int(x / self._cell_w)
        row = self._row_at_y(y)
        if row < 0:
            return 0
        day = row * 7 + col + 1 - self._first_wd
        return day if 1 <= day <= self._last_day else 0

    def _get_stack(self) -> dict[int, int]:
        """计算每个任务的堆叠行 (task_id → row_index)，跨月任务按裁剪后范围计算."""
        stack: dict[int, list[int]] = {}
        rows: dict[int, int] = {}
        for tid, sd, ed, title in sorted(self._tasks, key=lambda t: (t[1], t[2])):
            s, e = self._clamp(sd, ed)
            if s <= 0:
                continue
            assigned = None
            for row_idx in range(20):
                if not any(d in stack and row_idx in stack[d] for d in range(s, e + 1)):
                    assigned = row_idx
                    break
            if assigned is None:
                assigned = 0
            rows[tid] = assigned
            for d in range(s, e + 1):
                stack.setdefault(d, []).append(assigned)
        return rows

    # ── 绘制 ────────────────────────────────────────────

    def paintEvent(self, event):
        self._layout()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, cw = self.width(), self._cell_w

        # 背景
        painter.fillRect(0, 0, w, self.height(), QColor("#1a1a2e"))

        # 星期头
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        for col, name in enumerate(["一", "二", "三", "四", "五", "六", "日"]):
            painter.setPen(QColor("#f44336" if col >= 5 else "#808098"))
            painter.drawText(QRectF(col * cw, 0, cw, self._header_h), Qt.AlignmentFlag.AlignCenter, name)

        painter.setPen(QPen(QColor("#2a2a40"), 1))
        painter.drawLine(0, self._header_h, w, self._header_h)

        # ── 格子 + 日期 + 加号 ──
        for r in range(6):
            row_h = self._row_heights[r]
            for c in range(7):
                day_num = r * 7 + c + 1 - self._first_wd
                x, y = c * cw, self._row_y(r)
                in_month = 1 <= day_num <= self._last_day

                painter.setPen(QPen(QColor("#2a2a40"), 1))
                painter.drawRect(QRectF(x, y, cw, row_h))
                if not in_month:
                    continue

                is_today = (self._year == self._today.year and
                            self._month == self._today.month and day_num == self._today.day)

                # ── 右上角：日期（圆与文字同一矩形，保证居中） ──
                if is_today:
                    day_rect = QRectF(x + cw - 32, y + 4, 28, 28)
                    path = QPainterPath()
                    path.addEllipse(day_rect)
                    painter.fillPath(path, QColor("#7c5cfc"))
                    painter.setPen(QColor("#ffffff"))
                else:
                    painter.setPen(QColor("#ffffff"))
                painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold if is_today else QFont.Weight.Medium))
                painter.drawText(day_rect if is_today else QRectF(x + cw - 32, y + 4, 28, 28),
                                 Qt.AlignmentFlag.AlignCenter, str(day_num))

                # ── 左上角：圆角矩形 + 按钮（线条绘制，保证像素级居中） ──
                is_hover_btn = (day_num == self._hover_day)
                t = self._plus_progress if is_hover_btn else 0.0
                bg_r = int(0x2A + (0x7C - 0x2A) * t)
                bg_g = int(0x2A + (0x5C - 0x2A) * t)
                bg_b = int(0x44 + (0xFC - 0x44) * t)
                fg_r = int(0x80 + (0xFF - 0x80) * t)
                fg_g = int(0x80 + (0xFF - 0x80) * t)
                fg_b = int(0x98 + (0xFF - 0x98) * t)
                plus_rect = QRectF(x + 4, y + 7, 20, 18)
                path2 = QPainterPath()
                path2.addRoundedRect(plus_rect, 4, 4)
                painter.fillPath(path2, QColor(bg_r, bg_g, bg_b))
                # + 号用两条线段绘制，中心对齐
                painter.setPen(QPen(QColor(fg_r, fg_g, fg_b), 2))
                cx_p = plus_rect.center().x()
                cy_p = plus_rect.center().y()
                painter.drawLine(QPointF(cx_p - 3.5, cy_p), QPointF(cx_p + 3.5, cy_p))
                painter.drawLine(QPointF(cx_p, cy_p - 3.5), QPointF(cx_p, cy_p + 3.5))

        # ── 任务条（按行分段绘制，跨行任务每行都显示） ──
        task_rows = self._get_stack()
        painter.setFont(QFont("Segoe UI", 10))
        for tid, sd, ed, title in self._tasks:
            s_day, e_day = self._clamp(sd, ed)
            if s_day <= 0:
                continue

            stack_row = task_rows.get(tid, 0)
            is_hover = (tid == self._hover_task_id)
            pen_color = "#7c5cfc" if is_hover else "#3a3a50"
            font_weight = QFont.Weight.Bold if is_hover else QFont.Weight.Normal

            # 拆分为每行的段：[(row, seg_start_day, seg_end_day)]
            segments = []
            cur_row = (s_day + self._first_wd - 1) // 7
            cur_day = s_day
            while cur_day <= e_day:
                row_last_idx = (cur_row + 1) * 7 - 1
                row_last_day = row_last_idx + 1 - self._first_wd
                seg_end = min(e_day, row_last_day)
                segments.append((cur_row, cur_day, seg_end))
                cur_day = seg_end + 1
                cur_row += 1

            for seg_idx, (seg_row, seg_start, seg_end) in enumerate(segments):
                s_col = (seg_start + self._first_wd - 1) % 7
                e_col = (seg_end + self._first_wd - 1) % 7
                bx = s_col * cw + 2
                by = self._row_y(seg_row) + 34 + stack_row * 22
                bw = (e_col - s_col + 1) * cw - 4
                bh = 19

                painter.setPen(QPen(QColor(pen_color), 1))
                painter.setBrush(QColor("#25253a"))
                path = QPainterPath()
                path.addRoundedRect(bx, by, bw, bh, 3, 3)
                painter.drawPath(path)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.fillRect(QRectF(bx + 1, by + 2, 3, bh - 4), QColor("#7c5cfc"))

                # 标题每段都画（跨行时每行第一格显示任务名，Notion 风格）
                painter.setPen(QColor("#e0e0e8"))
                painter.setFont(QFont("Segoe UI", 10, font_weight))
                text = title[:int(bw / 7.5)] + ".." if len(title) > int(bw / 7.5) else title
                painter.drawText(QRectF(bx + 8, by, bw - 14, bh),
                                 Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

                # 拖拽手柄：左边缘（第一段且开始日期在当月内）
                if is_hover and bw > 40 and seg_idx == 0 and self._task_left_draggable(sd):
                    painter.fillRect(QRectF(bx + 4, by + 2, 6, bh - 4), QColor(255, 255, 255, 60))
                # 拖拽手柄：右边缘（最后一段）
                if is_hover and bw > 40 and seg_idx == len(segments) - 1:
                    painter.fillRect(QRectF(bx + bw - 10, by + 2, 6, bh - 4), QColor(255, 255, 255, 60))

        painter.end()

    def _cell_pos(self, day_num: int):
        """返回 (row, col) 和 (x, y)."""
        idx = day_num + self._first_wd - 1
        row, col = idx // 7, idx % 7
        return row, col, (col * self._cell_w, self._row_y(row))

    # ── 鼠标 ────────────────────────────────────────────

    def _on_plus_anim(self, value: float):
        self._plus_progress = float(value)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        x, y = int(event.position().x()), int(event.position().y())
        new_day = self._day_at(x, y)
        if new_day != self._hover_day:
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

        # 右拉拖拽（延长结束日期）
        if self._drag_side_task_id is not None:
            nd = self._hover_day
            if nd > 0 and nd != self._drag_target_day:
                self._drag_target_day = nd
                for i, (tid, sd, ed, title) in enumerate(self._tasks):
                    if tid == self._drag_side_task_id:
                        new_end = date(self._year, self._month, nd)
                        if new_end < sd:
                            new_end = sd
                        self._tasks[i] = (tid, sd, new_end, title)
                        break
                self.update()
            return

        # 左拉拖拽（移动开始日期）
        if self._drag_left_task_id is not None:
            nd = self._hover_day
            if nd > 0 and nd != self._drag_left_target_day:
                self._drag_left_target_day = nd
                for i, (tid, sd, ed, title) in enumerate(self._tasks):
                    if tid == self._drag_left_task_id:
                        new_start = date(self._year, self._month, nd)
                        if new_start > ed:
                            new_start = ed
                        self._tasks[i] = (tid, new_start, ed, title)
                        break
                self.update()
            return

        old_ht = self._hover_task_id
        self._hover_task_id = None
        if self._hover_day > 0:
            task_rows = self._get_stack()
            _, _, (cx, cy) = self._cell_pos(self._hover_day)
            for tid, sd, ed, title in self._tasks:
                s_day, e_day = self._clamp(sd, ed)
                if not (s_day <= self._hover_day <= e_day):
                    continue
                sr = task_rows.get(tid, 0)
                ty = cy + 34 + sr * 22
                if ty <= y < ty + 20:
                    self._hover_task_id = tid
                    # 右边缘检测
                    _, e_day_c = self._clamp(sd, ed)
                    e_col = (e_day_c + self._first_wd - 1) % 7
                    ecx = e_col * self._cell_w
                    bar_right = ecx + self._cell_w
                    # 左边缘检测（仅开始日期在当月内的任务）
                    left_draggable = self._task_left_draggable(sd)
                    s_day_c, _ = self._clamp(sd, ed)
                    s_col = (s_day_c + self._first_wd - 1) % 7
                    bar_left = s_col * self._cell_w
                    if left_draggable and abs(x - bar_left) < 12:
                        self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
                    elif abs(x - bar_right) < 12:
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
        row = self._row_at_y(y)
        cx = col * self._cell_w
        cy = self._row_y(row) if row >= 0 else 0
        if (cx + 4 <= x <= cx + 24 and
                cy + 7 <= y <= cy + 25 and self._hover_day == day):
            if self.on_cell_add:
                self.on_cell_add(self._year, self._month, day)
            return

        # 任务点击 + 拖拽
        task_rows = self._get_stack()
        _, _, (cx, cy) = self._cell_pos(day)
        for tid, sd, ed, title in self._tasks:
            s_day, e_day = self._clamp(sd, ed)
            if not (s_day <= day <= e_day):
                continue
            sr = task_rows.get(tid, 0)
            ty = cy + 34 + sr * 22
            if ty <= y < ty + 20:
                _, e_day_c = self._clamp(sd, ed)
                e_col = (e_day_c + self._first_wd - 1) % 7
                ecx = e_col * self._cell_w
                bar_right = ecx + self._cell_w

                # 右边缘 → 右拉
                if abs(x - bar_right) < 12:
                    self._drag_side_task_id = tid
                    self._drag_target_day = e_day
                    return
                # 左边缘 → 左拉（仅开始日期在当月内）
                if self._task_left_draggable(sd):
                    s_day_c, _ = self._clamp(sd, ed)
                    s_col = (s_day_c + self._first_wd - 1) % 7
                    bar_left = s_col * self._cell_w
                    if abs(x - bar_left) < 12:
                        self._drag_left_task_id = tid
                        self._drag_left_target_day = s_day_c
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
        if self._drag_left_task_id is not None and self._drag_left_target_day is not None:
            if self.on_task_left_drag:
                self.on_task_left_drag(self._drag_left_task_id, self._drag_left_target_day)
            self._drag_left_task_id = None
            self._drag_left_target_day = None
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        x = int(event.position().x())
        y = int(event.position().y())
        day = self._day_at(x, y)
        if not (day > 0 and self.on_cell_add):
            return

        # 跳过 + 按钮区域
        col = int(x / self._cell_w)
        row = self._row_at_y(y)
        cx2 = col * self._cell_w
        cy2 = self._row_y(row) if row >= 0 else 0
        if (cx2 + 4 <= x <= cx2 + 24 and
                cy2 + 7 <= y <= cy2 + 25):
            return

        _, _, (cx, cy) = self._cell_pos(day)
        task_rows = self._get_stack()
        on_task = False
        for tid, sd, ed, title in self._tasks:
            s_day, e_day = self._clamp(sd, ed)
            if not (s_day <= day <= e_day):
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
