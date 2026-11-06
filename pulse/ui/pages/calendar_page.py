"""日历页面 —— Notion 风格月历 + 弹出创建 + 模态详情."""

from datetime import date, datetime
from typing import Optional

from PyQt6.QtCore import QTimer, Qt  # type: ignore
from PyQt6.QtWidgets import (  # type: ignore
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from pulse.db.repository import Repository
from pulse.ui.widgets.notion_grid import NotionGrid
from pulse.ui.widgets.task_popup import TaskCreatePopup
from pulse.ui.widgets.task_detail_dialog import TaskDetailDialog

_MONTH_NAMES = ["", "一月", "二月", "三月", "四月", "五月", "六月",
                "七月", "八月", "九月", "十月", "十一月", "十二月"]


class CalendarPage(QWidget):
    """日历页面 —— Notion 风格."""

    def __init__(self, repo: Optional[Repository] = None):
        super().__init__()
        self.setObjectName('calendarPage')
        self._repo = repo
        self._today = date.today()
        self._view_year = self._today.year
        self._view_month = self._today.month

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 16)
        root.setSpacing(16)

        # ── 导航 ──
        self._build_nav(root)

        # ── 网格（放入滚动区：任务多的行保持自然高度，纵向滚轮查看，不再挤压其他行） ──
        self._grid = NotionGrid()
        self._grid.on_task_click = self._open_detail
        self._grid.on_cell_add = self._on_cell_add
        self._grid.on_task_drag = self._on_task_drag
        self._grid.on_task_left_drag = self._on_task_left_drag

        self._grid_scroll = QScrollArea()
        self._grid_scroll.setWidgetResizable(True)
        self._grid_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._grid_scroll.setWidget(self._grid)
        root.addWidget(self._grid_scroll, stretch=1)

        # ── 弹出创建 ──
        self._popup = TaskCreatePopup(self)

        self._refresh_grid()

        # ── 跨零点自动刷新"今日"高亮 ──
        self._date_check = QTimer(self)
        self._date_check.timeout.connect(self._check_date_change)
        self._date_check.start(30000)  # 每 30 秒检查一次

    def _check_date_change(self):
        """日期变化时（跨零点）刷新日历."""
        today = date.today()
        if today != self._today:
            self._today = today
            self._refresh_grid()

    def set_repo(self, repo: Repository) -> None:
        self._repo = repo
        self._refresh_grid()

    def refresh(self):
        """页面切换时调用的公开刷新入口."""
        self._refresh_grid()

    # ── 导航 ──────────────────────────────────────────

    def _build_nav(self, layout: QVBoxLayout):
        heading = QLabel('日历')
        heading.setObjectName('calendarHeading')
        layout.addWidget(heading)
        row = QHBoxLayout()
        row.setSpacing(6)

        today_btn = QPushButton("今天")
        today_btn.setToolTip('回到本月')
        today_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        today_btn.clicked.connect(self._go_today)

        self._nav_label = QLabel()
        self._nav_label.setObjectName('calendarMonth')

        prev_btn = QPushButton("‹")
        prev_btn.setFixedSize(32, 32)
        prev_btn.setToolTip('上个月')
        prev_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        prev_btn.clicked.connect(self._prev_month)

        next_btn = QPushButton("›")
        next_btn.setFixedSize(32, 32)
        next_btn.setToolTip('下个月')
        next_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        next_btn.clicked.connect(self._next_month)

        row.addWidget(self._nav_label)
        row.addStretch()
        row.addWidget(prev_btn)
        row.addWidget(today_btn)
        row.addWidget(next_btn)
        new_btn = QPushButton('新建任务')
        new_btn.setObjectName('calendarNew')
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.clicked.connect(self._new_task)
        row.addSpacing(12)
        row.addWidget(new_btn)
        layout.addLayout(row)

    # ── 刷新 ───────────────────────────────────────────

    def _new_task(self):
        today = date.today()
        day = today.day if (self._view_year, self._view_month) == (today.year, today.month) else 1
        self._on_cell_add(self._view_year, self._view_month, day)

    def _refresh_grid(self):
        self._nav_label.setText(f"{_MONTH_NAMES[self._view_month]} {self._view_year}")
        if self._repo:
            tasks = self._repo.get_tasks_by_month(self._view_year, self._view_month)
            # 清单进度（任务条上显示 n/m 或 ✓）
            summaries = self._repo.get_checklist_summaries([row[0].id for row in tasks]) if tasks else {}
            self._grid.set_data(self._view_year, self._view_month, tasks, checklist_summaries=summaries)

    # ── 导航 ───────────────────────────────────────────

    def _go_today(self):
        self._today = date.today()
        self._view_year = self._today.year
        self._view_month = self._today.month
        self._refresh_grid()

    def _prev_month(self):
        self._view_month -= 1
        if self._view_month < 1:
            self._view_month = 12
            self._view_year -= 1
        self._refresh_grid()

    def _next_month(self):
        self._view_month += 1
        if self._view_month > 12:
            self._view_month = 1
            self._view_year += 1
        self._refresh_grid()

    # ── 新建任务 ─────────────────────────────────────

    def _on_cell_add(self, year: int, month: int, day: int):
        """双击或 + → 在日历页面正中间弹出创建卡片."""
        # 计算屏幕全局坐标（Popup 窗口用全局坐标定位）
        center = self.mapToGlobal(self.rect().center())
        gx = int(center.x() - 140)
        gy = int(center.y() - 70)
        self._popup.show_at(gx, gy, lambda title: self._do_create(year, month, day, title))

    def _do_create(self, year: int, month: int, day: int, title: str):
        if not self._repo:
            return
        task = self._repo.create_task(date(year, month, day), title)
        self._open_detail(task.id)
        self._refresh_grid()

    # ── 任务详情（模态对话框） ──────────────────────────

    def _open_detail(self, task_id: int):
        if not self._repo:
            return
        dlg = TaskDetailDialog(task_id, self._repo, self)
        dlg.exec()
        self._refresh_grid()

    # ── 拖拽延长 ───────────────────────────────────────

    def _on_task_drag(self, task_id: int, new_end_day: int):
        if not self._repo:
            return
        end_date = date(self._view_year, self._view_month, new_end_day)
        with self._repo.session() as s:
            from pulse.db.models import CalendarTask
            s.query(CalendarTask).filter(CalendarTask.id == task_id).update({"end_date": end_date})
        self._refresh_grid()

    def _on_task_left_drag(self, task_id: int, new_start_day: int):
        """左拉移动任务开始日期."""
        if not self._repo:
            return
        start_date = date(self._view_year, self._view_month, new_start_day)
        with self._repo.session() as s:
            from pulse.db.models import CalendarTask
            task = s.query(CalendarTask).filter(CalendarTask.id == task_id).first()
            if not task:
                return
            # 开始日期不能超过结束日期
            end = task.end_date or task.date
            if start_date > end:
                start_date = end
            s.query(CalendarTask).filter(CalendarTask.id == task_id).update({"date": start_date})
        self._refresh_grid()
