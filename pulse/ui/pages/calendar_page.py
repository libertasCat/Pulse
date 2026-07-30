"""日历页面 —— Notion 风格月历 + 任务详情 + 字段 + 评论."""

import calendar
from datetime import date, datetime
from typing import Optional

from PyQt6.QtCore import Qt  # type: ignore
from PyQt6.QtGui import QColor, QFont  # type: ignore
from PyQt6.QtWidgets import (  # type: ignore
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget,
)

from pulse.db.repository import Repository


class _DayCell(QFrame):
    """日历网格中一天的格子."""

    def __init__(self, day_num: int, is_current_month: bool, is_today: bool, parent=None):
        super().__init__(parent)
        self.day_num = day_num
        self.setObjectName("card")
        self.setFixedSize(120, 110)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        border = "#7c5cfc" if is_today else "transparent"
        bg = "#2a2a44" if is_today else "#25253a"
        self.setStyleSheet(
            f"QFrame#card {{ background: {bg}; border: 2px solid {border}; "
            f"border-radius: 8px; padding: 4px; }}"
            f"QFrame#card:hover {{ border-color: #7c5cfc; }}"
        )

        lo = QVBoxLayout(self)
        lo.setContentsMargins(6, 4, 6, 4)
        lo.setSpacing(2)

        color = "#ffffff" if is_current_month else "#606080"
        self._date_label = QLabel(str(day_num))
        self._date_label.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {color}; background: transparent;")
        lo.addWidget(self._date_label)

        self._task_layout = QVBoxLayout()
        self._task_layout.setSpacing(2)
        lo.addLayout(self._task_layout)

    def clear_tasks(self):
        while self._task_layout.count():
            item = self._task_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def add_task_bar(self, text: str, task_id: int, callback):
        btn = QPushButton(text[:18] + ".." if len(text) > 18 else text)
        btn.setFixedHeight(20)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton { background: #7c5cfc; border: none; border-radius: 3px; "
            "color: #fff; font-size: 10px; text-align: left; padding: 0 4px; }"
            "QPushButton:hover { background: #6a4acc; }"
        )
        btn.clicked.connect(lambda: callback(task_id))
        self._task_layout.addWidget(btn)


class CalendarPage(QWidget):
    """日历页面 —— 月历网格 + 任务详情面板."""

    def __init__(self, repo: Optional[Repository] = None):
        super().__init__()
        self._repo = repo
        self._today = date.today()
        self._view_year = self._today.year
        self._view_month = self._today.month
        self._selected_task_id: Optional[int] = None

        self._tasks_cache: dict[int, list] = {}  # date.day -> list of task tuples

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # ── Left: Month Grid ──
        left = QVBoxLayout()
        self._build_nav(left)
        self._build_weekday_header(left)
        self._build_grid(left)
        root.addLayout(left, stretch=2)

        # ── Right: Task Detail Panel ──
        self._detail_panel = QFrame()
        self._detail_panel.setObjectName("card")
        self._detail_panel.setFixedWidth(380)
        self._detail_panel.setVisible(False)
        dp = QVBoxLayout(self._detail_panel)
        dp.setSpacing(8)

        # title
        dp.addWidget(QLabel("任务详情", styleSheet="font-size: 15px; font-weight: 700;"))

        self._detail_title = QLineEdit()
        self._detail_title.setStyleSheet(
            "font-size: 16px; font-weight: 600; padding: 6px; border: none; "
            "border-bottom: 1px solid #3a3a50; background: transparent; color: #fff;"
        )
        self._detail_title.editingFinished.connect(self._save_task_title)
        dp.addWidget(self._detail_title)

        # fields
        dp.addWidget(QLabel("字段", styleSheet="font-size: 12px; color: #808098; margin-top: 8px;"))
        self._fields_container = QVBoxLayout()
        dp.addLayout(self._fields_container)

        add_field_btn = QPushButton("+ 添加字段")
        add_field_btn.setStyleSheet(
            "QPushButton { background: #3a3a5a; border: none; border-radius: 4px; "
            "padding: 6px; color: #a0a0b8; font-size: 12px; }"
            "QPushButton:hover { background: #4a4a6a; color: #fff; }"
        )
        add_field_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_field_btn.clicked.connect(self._add_new_field)
        dp.addWidget(add_field_btn)

        # comments
        dp.addWidget(QLabel("评论", styleSheet="font-size: 12px; color: #808098; margin-top: 8px;"))

        self._comments_scroll = QScrollArea()
        self._comments_scroll.setWidgetResizable(True)
        self._comments_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._comments_scroll.setStyleSheet("background: transparent;")
        self._comments_container = QWidget()
        self._comments_layout = QVBoxLayout(self._comments_container)
        self._comments_layout.setSpacing(4)
        self._comments_scroll.setWidget(self._comments_container)
        dp.addWidget(self._comments_scroll, stretch=1)

        # comment input
        comment_row = QHBoxLayout()
        self._comment_input = QLineEdit()
        self._comment_input.setPlaceholderText("写评论...")
        self._comment_input.setStyleSheet(
            "padding: 6px; border-radius: 4px; background: #1e1e34; color: #fff; border: 1px solid #3a3a50;"
        )
        self._comment_input.returnPressed.connect(self._post_comment)
        comment_send = QPushButton("发送")
        comment_send.setStyleSheet(
            "QPushButton { background: #7c5cfc; border: none; border-radius: 4px; "
            "padding: 6px 14px; color: #fff; font-weight: 600; font-size: 12px; }"
        )
        comment_send.setCursor(Qt.CursorShape.PointingHandCursor)
        comment_send.clicked.connect(self._post_comment)
        comment_row.addWidget(self._comment_input)
        comment_row.addWidget(comment_send)
        dp.addLayout(comment_row)

        root.addWidget(self._detail_panel, alignment=Qt.AlignmentFlag.AlignTop)

        self._refresh_grid()
        self._refresh_all_date_labels()

    def set_repo(self, repo: Repository) -> None:
        self._repo = repo
        self._refresh_grid()

    # ── Navigation ──────────────────────────────────────────

    def _build_nav(self, layout: QVBoxLayout):
        row = QHBoxLayout()
        row.setSpacing(8)

        today_btn = QPushButton("今天")
        today_btn.setStyleSheet(
            "QPushButton { background: #7c5cfc; border: none; border-radius: 4px; "
            "padding: 6px 14px; color: #fff; font-weight: 600; font-size: 12px; }"
            "QPushButton:hover { background: #6a4acc; }"
        )
        today_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        today_btn.clicked.connect(self._go_today)

        self._nav_label = QLabel()
        self._nav_label.setStyleSheet("font-size: 18px; font-weight: 700;")

        prev_btn = QPushButton("◀")
        prev_btn.setFixedSize(32, 32)
        prev_btn.setStyleSheet("QPushButton { border: none; border-radius: 4px; font-size: 14px; }"
                                "QPushButton:hover { background: #2a2a44; }")
        prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prev_btn.clicked.connect(self._prev_month)

        next_btn = QPushButton("▶")
        next_btn.setFixedSize(32, 32)
        next_btn.setStyleSheet("QPushButton { border: none; border-radius: 4px; font-size: 14px; }"
                                "QPushButton:hover { background: #2a2a44; }")
        next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        next_btn.clicked.connect(self._next_month)

        row.addWidget(today_btn)
        row.addSpacing(8)
        row.addWidget(prev_btn)
        row.addWidget(self._nav_label)
        row.addWidget(next_btn)
        row.addStretch()
        layout.addLayout(row)

    def _build_weekday_header(self, layout: QVBoxLayout):
        row = QHBoxLayout()
        row.setSpacing(4)
        for name in ["一", "二", "三", "四", "五", "六", "日"]:
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 12px; color: #808098; font-weight: 600; padding: 4px 0;")
            row.addWidget(lbl)
        layout.addLayout(row)

    def _build_grid(self, layout: QVBoxLayout):
        self._grid = QGridLayout()
        self._grid.setSpacing(4)
        self._cells: dict[int, _DayCell] = {}
        for r in range(6):
            for c in range(7):
                cell = _DayCell(0, False, False)
                cell.setVisible(False)
                cell.mouseDoubleClickEvent = lambda e, day=r * 7 + c + 1: self._on_cell_double_click(day) if False else None
                self._grid.addWidget(cell, r, c)
        layout.addLayout(self._grid)

    # ── Data Refresh ────────────────────────────────────────

    def _refresh_nav_label(self):
        month_names = ["", "一月", "二月", "三月", "四月", "五月", "六月",
                       "七月", "八月", "九月", "十月", "十一月", "十二月"]
        self._nav_label.setText(f"{month_names[self._view_month]} {self._view_year}")

    def _refresh_grid(self):
        if not self._repo:
            return
        self._refresh_nav_label()
        self._tasks_cache.clear()

        # Fetch tasks for this month
        month_tasks = self._repo.get_tasks_by_month(self._view_year, self._view_month)
        for row in month_tasks:
            task, field_count, comment_count = row
            d = task.date.day
            if d not in self._tasks_cache:
                self._tasks_cache[d] = []
            self._tasks_cache[d].append(task)

        _, last_day = calendar.monthrange(self._view_year, self._view_month)
        first_weekday = date(self._view_year, self._view_month, 1).weekday()

        for r in range(6):
            for c in range(7):
                cell = self._grid.itemAtPosition(r, c).widget()
                day_num = r * 7 + c + 1 - first_weekday
                in_month = 1 <= day_num <= last_day
                cell.setVisible(True)
                cell.clear_tasks()

                if in_month:
                    is_today = (self._view_year == self._today.year and
                                self._view_month == self._today.month and
                                day_num == self._today.day)
                    cell.day_num = day_num
                    cell._date_label.setText(str(day_num))
                    cell.setStyleSheet(
                        f"QFrame#card {{ background: {'#2a2a44' if is_today else '#25253a'}; "
                        f"border: 2px solid {'#7c5cfc' if is_today else 'transparent'}; "
                        f"border-radius: 8px; padding: 4px; }}"
                        f"QFrame#card:hover {{ border-color: #7c5cfc; }}"
                    )
                    cell._date_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #ffffff; background: transparent;")

                    # 绑定双击
                    orig = cell.mouseDoubleClickEvent
                    cell.mouseDoubleClickEvent = lambda e, d=day_num: self._on_cell_double_click(d)

                    # 显示任务条
                    tasks = self._tasks_cache.get(day_num, [])
                    for task in tasks[:4]:
                        cell.add_task_bar(task.title, task.id, self._select_task)
                    if len(tasks) > 4:
                        more = QLabel(f"+{len(tasks) - 4} 更多")
                        more.setStyleSheet("color: #606080; font-size: 9px; background: transparent;")
                        cell._task_layout.addWidget(more)
                else:
                    cell.day_num = 0
                    cell._date_label.setText(str(day_num))
                    cell._date_label.setStyleSheet("font-size: 14px; font-weight: 400; color: #3a3a50; background: transparent;")
                    for w in range(cell._task_layout.count()):
                        item = cell._task_layout.itemAt(w)
                        if item.widget():
                            item.widget().setVisible(False)

    def _refresh_all_date_labels(self):
        """(Unused) – kept for compatibility with earlier design."""
        pass

    def _go_today(self):
        self._view_year = self._today.year
        self._view_month = self._today.month
        self._selected_task_id = None
        self._detail_panel.setVisible(False)
        self._refresh_grid()

    def _prev_month(self):
        if self._view_month == 1:
            self._view_year -= 1
            self._view_month = 12
        else:
            self._view_month -= 1
        self._selected_task_id = None
        self._detail_panel.setVisible(False)
        self._refresh_grid()

    def _next_month(self):
        if self._view_month == 12:
            self._view_year += 1
            self._view_month = 1
        else:
            self._view_month += 1
        self._selected_task_id = None
        self._detail_panel.setVisible(False)
        self._refresh_grid()

    def _on_cell_double_click(self, day: int):
        if not self._repo or day <= 0:
            return
        target = date(self._view_year, self._view_month, day)
        task = self._repo.create_task(target)
        self._tasks_cache[day] = self._tasks_cache.get(day, []) + [task]
        self._select_task(task.id)
        self._refresh_grid()

    # ── Task Detail ────────────────────────────────────────

    def _select_task(self, task_id: int):
        self._selected_task_id = task_id
        self._detail_panel.setVisible(True)

        if not self._repo:
            return
        tasks = self._repo.get_tasks_by_date(date(self._view_year, self._view_month, 1))
        task = None
        for t in tasks:
            if t.id == task_id:
                task = t
                break
        if not task:
            return

        self._detail_title.setText(task.title)

        # 清除旧字段
        while self._fields_container.count():
            item = self._fields_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for field in task.fields:
            self._add_field_widget(field.id, field.content)

        # 清除旧评论
        while self._comments_layout.count():
            item = self._comments_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        comments = self._repo.get_comments(task_id)
        for c in comments:
            self._add_comment_widget(c.author, c.content, c.created_at)

        # 刷新网格
        self._refresh_grid()

    def _add_field_widget(self, field_id: int, content: str):
        frame = QFrame()
        frame.setStyleSheet("QFrame { background: #1e1e34; border-radius: 6px; padding: 4px; }")
        lo = QHBoxLayout(frame)
        lo.setContentsMargins(4, 2, 4, 2)

        edit = QTextEdit()
        edit.setPlainText(content)
        edit.setFixedHeight(50)
        edit.setStyleSheet(
            "QTextEdit { background: transparent; border: none; color: #e0e0e8; "
            "font-size: 13px; padding: 2px; }"
        )
        edit.textChanged.connect(lambda fid=field_id, e=edit: self._on_field_changed(fid, e.toPlainText()))

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(20, 20)
        del_btn.setStyleSheet("QPushButton { background: transparent; border: none; color: #606080; font-size: 12px; }"
                               "QPushButton:hover { color: #f44336; }")
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(lambda: self._delete_field(field_id))

        lo.addWidget(edit, stretch=1)
        lo.addWidget(del_btn)
        self._fields_container.addWidget(frame)

    def _add_comment_widget(self, author: str, content: str, created_at: datetime):
        time_str = created_at.strftime("%m/%d %H:%M") if created_at else ""
        text = f"<b>{author}</b>  <span style='color:#606080;font-size:11px;'>{time_str}</span><br>{content}"
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 12px; padding: 4px 0; color: #c0c0d0; background: transparent;")
        self._comments_layout.addWidget(lbl)

    def _save_task_title(self):
        if self._selected_task_id and self._repo:
            self._repo.update_task_title(self._selected_task_id, self._detail_title.text())
            self._refresh_grid()

    def _on_field_changed(self, field_id: int, content: str):
        if self._repo:
            self._repo.update_task_field(field_id, content)

    def _add_new_field(self):
        if self._selected_task_id and self._repo:
            f = self._repo.add_task_field(self._selected_task_id)
            self._add_field_widget(f.id, "")

    def _delete_field(self, field_id: int):
        if self._repo:
            self._repo.delete_task_field(field_id)
            # rebuild fields
            if self._selected_task_id:
                self._select_task(self._selected_task_id)

    def _post_comment(self):
        text = self._comment_input.text().strip()
        if not text or not self._selected_task_id or not self._repo:
            return
        self._repo.add_comment(self._selected_task_id, text)
        self._comment_input.clear()
        self._select_task(self._selected_task_id)
