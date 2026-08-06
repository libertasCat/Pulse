"""统计页面 —— 日视图 / 周视图 / 月视图 / 对比."""

from datetime import date, timedelta
from typing import Optional

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from pulse.db.repository import Repository
from pulse.ui.widgets.charts import (
    HorizontalBarChart, HourlyTimeline, HeatmapCalendar,
)
from pulse.utils.icon_cache import get_app_icon
from pulse.utils.process_names import strip_ext

_BAR_COLORS = [
    "#7c5cfc", "#2196F3", "#4CAF50", "#FF9800",
    "#E91E63", "#00BCD4", "#9C27B0", "#FF5722",
]


class StatsPage(QWidget):
    """统计页面 —— 四标签：日 / 周 / 月 / 对比."""

    def __init__(self, repo: Optional[Repository] = None):
        super().__init__()
        self._repo = repo
        self._today = date.today()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        self._build_header(layout)
        self._build_tab_bar(layout)
        self._build_tab_pages(layout)

        self._refresh()

    def set_repo(self, repo: Repository) -> None:
        self._repo = repo
        self._refresh()

    # ── 头部 ────────────────────────────────────────────

    def _build_header(self, layout: QVBoxLayout):
        title = QLabel("统计")
        title.setObjectName("pageTitle")
        self._subtitle = QLabel("")
        self._subtitle.setObjectName("pageSubtitle")
        row = QHBoxLayout()
        row.addWidget(title)
        row.addWidget(self._subtitle, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(row)

    # ── 标签栏 ──────────────────────────────────────────

    def _build_tab_bar(self, layout: QVBoxLayout):
        bar = QFrame()
        bar.setObjectName("card")
        bar.setFixedHeight(44)
        lo = QHBoxLayout(bar)
        lo.setContentsMargins(4, 4, 4, 4)
        lo.setSpacing(2)

        self._tab_group = QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self._tab_group.idClicked.connect(self._switch_tab)

        tabs = [(0, "日视图"), (1, "周视图"), (2, "月视图"), (3, "对比")]
        for tid, tname in tabs:
            btn = QPushButton(tname)
            btn.setCheckable(True)
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._TAB_STYLE)
            self._tab_group.addButton(btn, tid)
            lo.addWidget(btn)
        lo.addStretch()
        layout.addWidget(bar)
        if self._tab_group.buttons():
            self._tab_group.buttons()[0].setChecked(True)

    _TAB_STYLE = (
        "QPushButton { background: transparent; border: none; border-radius: 6px; "
        "padding: 4px 20px; font-size: 13px; color: #808098; }"
        "QPushButton:hover { background: #2a2a44; }"
        "QPushButton:checked { background: #7c5cfc; color: #ffffff; font-weight: 600; }"
    )

    # ── 标签页 ──────────────────────────────────────────

    def _build_tab_pages(self, layout: QVBoxLayout):
        self._pages = []

        # ---- Tab 0: 日视图 ----
        p0 = QWidget()
        lo0 = QVBoxLayout(p0)
        lo0.setContentsMargins(0, 0, 0, 0)

        # 日导航
        day_nav = QHBoxLayout()
        self._day_prev = QPushButton("◀")
        self._day_prev.setFixedSize(28, 28)
        self._day_prev.setStyleSheet("QPushButton { border: none; border-radius: 4px; color: #a0a0b8; font-size: 12px; }"
                                      "QPushButton:hover { background: #2a2a44; }")
        self._day_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._day_prev.clicked.connect(lambda: (setattr(self, '_day_offset', self._day_offset - 1), self._update_day_view()))
        self._day_next = QPushButton("▶")
        self._day_next.setFixedSize(28, 28)
        self._day_next.setStyleSheet("QPushButton { border: none; border-radius: 4px; color: #a0a0b8; font-size: 12px; }"
                                      "QPushButton:hover { background: #2a2a44; }")
        self._day_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._day_next.clicked.connect(lambda: (setattr(self, '_day_offset', self._day_offset + 1), self._update_day_view()))
        day_nav.addWidget(self._day_prev)
        self._day_label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self._day_label.setStyleSheet("font-size: 13px; font-weight: 600;")
        day_nav.addWidget(self._day_label, stretch=1)
        day_nav.addWidget(self._day_next)
        lo0.addLayout(day_nav)

        lo0.addWidget(QLabel("24 小时活跃度", styleSheet="font-size:14px;font-weight:600;margin-bottom:4px;"))
        self._hourly_chart = HourlyTimeline()
        self._hourly_chart.setFixedHeight(160)
        lo0.addWidget(self._hourly_chart)

        lo0.addWidget(QLabel("", styleSheet="margin:4px 0;"))

        lo0.addWidget(QLabel("今日应用排行", styleSheet="font-size:14px;font-weight:600;margin-bottom:4px;"))
        self._day_bar = HorizontalBarChart()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background:transparent;")
        scroll.setWidget(self._day_bar)
        lo0.addWidget(scroll, stretch=1)
        self._pages.append(p0)

        # ---- Tab 1: 周视图 ----
        p1 = QWidget()
        lo1 = QVBoxLayout(p1)
        lo1.setContentsMargins(0, 0, 0, 0)

        self._week_nav = QHBoxLayout()
        self._week_label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self._week_label.setStyleSheet("font-size:14px;font-weight:600;")
        self._week_prev = QPushButton("<")
        self._week_prev.setFixedSize(30, 30)
        self._week_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._week_prev.setStyleSheet("background:#2a2a44;border:none;border-radius:4px;color:#fff;")
        self._week_prev.clicked.connect(lambda: self._shift_week(-1))
        self._week_next = QPushButton(">")
        self._week_next.setFixedSize(30, 30)
        self._week_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._week_next.setStyleSheet("background:#2a2a44;border:none;border-radius:4px;color:#fff;")
        self._week_next.clicked.connect(lambda: self._shift_week(1))

        self._week_nav.addStretch()
        self._week_nav.addWidget(self._week_prev)
        self._week_nav.addWidget(self._week_label)
        self._week_nav.addWidget(self._week_next)
        self._week_nav.addStretch()
        lo1.addLayout(self._week_nav)

        self._week_chart = HorizontalBarChart()
        self._week_chart.setFixedHeight(280)
        lo1.addWidget(self._week_chart)
        self._week_total_label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self._week_total_label.setStyleSheet("color:#808098;font-size:12px;")
        lo1.addWidget(self._week_total_label)
        lo1.addStretch()
        self._pages.append(p1)

        # ---- Tab 2: 月视图 ----
        p2 = QWidget()
        lo2 = QVBoxLayout(p2)
        lo2.setContentsMargins(0, 0, 0, 0)

        self._month_nav = QHBoxLayout()
        self._month_label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self._month_label.setStyleSheet("font-size:14px;font-weight:600;")
        self._month_prev = QPushButton("<")
        self._month_prev.setFixedSize(30, 30)
        self._month_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._month_prev.setStyleSheet("background:#2a2a44;border:none;border-radius:4px;color:#fff;")
        self._month_prev.clicked.connect(lambda: self._shift_month(-1))
        self._month_next = QPushButton(">")
        self._month_next.setFixedSize(30, 30)
        self._month_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._month_next.setStyleSheet("background:#2a2a44;border:none;border-radius:4px;color:#fff;")
        self._month_next.clicked.connect(lambda: self._shift_month(1))

        self._month_nav.addStretch()
        self._month_nav.addWidget(self._month_prev)
        self._month_nav.addWidget(self._month_label)
        self._month_nav.addWidget(self._month_next)
        self._month_nav.addStretch()
        lo2.addLayout(self._month_nav)

        self._heatmap = HeatmapCalendar()
        self._heatmap.setFixedHeight(320)
        lo2.addWidget(self._heatmap)
        self._month_total_label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self._month_total_label.setStyleSheet("color:#808098;font-size:12px;")
        lo2.addWidget(self._month_total_label)
        lo2.addStretch()
        self._pages.append(p2)

        # ---- Tab 3: 对比 ----
        p3 = QWidget()
        lo3 = QVBoxLayout(p3)
        lo3.setContentsMargins(0, 0, 0, 0)

        lo3.addWidget(QLabel("本周 vs 上周", styleSheet="font-size:14px;font-weight:600;margin-bottom:8px;"))
        self._compare_chart = HorizontalBarChart()
        self._compare_chart.setFixedHeight(300)
        lo3.addWidget(self._compare_chart)
        self._compare_label = QLabel("", alignment=Qt.AlignmentFlag.AlignCenter)
        self._compare_label.setStyleSheet("color:#808098;font-size:12px;")
        lo3.addWidget(self._compare_label)
        lo3.addStretch()
        self._pages.append(p3)

        # 只显示第一个
        for i, p in enumerate(self._pages):
            layout.addWidget(p, stretch=1)
            if i != 0:
                p.setVisible(False)

        self._day_offset = 0
        self._week_offset = 0
        self._month_offset = 0

    def _switch_tab(self, tab_id: int):
        for i, p in enumerate(self._pages):
            p.setVisible(i == tab_id)
        self._refresh()

    # ── 刷新 ─────────────────────────────────────────────

    def refresh(self):
        """页面切换时调用的公开刷新入口（异常兜底，防止偶现崩溃）. """
        try:
            self._refresh()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("统计页刷新异常: %s", e)

    def _refresh(self):
        if not self._repo:
            return
        self._today = date.today()
        self._update_day_view()
        self._update_week_view()
        self._update_month_view()
        self._update_compare_view()

    def _update_day_view(self):
        target = self._today + timedelta(days=self._day_offset)
        self._day_label.setText(target.strftime("%Y-%m-%d  %a"))
        total = self._repo.get_total_duration_by_date(target)
        h, m = total // 3600, (total % 3600) // 60
        self._subtitle.setText(f"{target.isoformat()}  ·  总 {h}h {m:02d}m")

        hourly = self._repo.get_hourly_breakdown(target)
        self._hourly_chart.set_data([h["total_seconds"] for h in hourly])

        # Top 应用
        apps = self._repo.get_usage_summary_by_date(target, "process_name")
        data = []
        for i, app in enumerate(apps[:10]):
            raw_name = app["name"]
            disp_name = strip_ext(raw_name)
            try:
                exe_path = self._repo.get_latest_exe_path(raw_name)
            except Exception:
                exe_path = None
            icon = get_app_icon(raw_name, exe_path)
            data.append((disp_name, app["total_seconds"], _BAR_COLORS[i % 8], icon))
        self._day_bar.set_data(data)

    def _update_week_view(self):
        monday = self._today - timedelta(days=self._today.weekday())
        monday += timedelta(weeks=self._week_offset)
        self._week_label.setText(f"{monday.strftime('%m/%d')} - {(monday + timedelta(days=6)).strftime('%m/%d')}")

        days = self._repo.get_daily_summaries(monday, 7)
        names = [(monday + timedelta(days=i)).strftime("%a %m/%d") for i in range(7)]
        data = []
        total = 0
        for i, d in enumerate(days):
            data.append((names[i], d["total_seconds"], _BAR_COLORS[i % 8], None))
            total += d["total_seconds"]
        self._week_chart.set_data(data)
        h, m = total // 3600, (total % 3600) // 60
        self._week_total_label.setText(f"本周合计: {h}h {m:02d}m")

    def _update_month_view(self):
        y = self._today.year
        m = self._today.month + self._month_offset
        while m < 1:
            y -= 1
            m += 12
        while m > 12:
            y += 1
            m -= 12

        self._month_label.setText(f"{y}年{m}月")
        totals = self._repo.get_daily_totals_for_month(y, m)
        self._heatmap.set_data(y, m, totals)

        total = sum(t["total_seconds"] for t in totals)
        h, m2 = total // 3600, (total % 3600) // 60
        self._month_total_label.setText(f"本月合计: {h}h {m2:02d}m")

    def _update_compare_view(self):
        monday = self._today - timedelta(days=self._today.weekday())
        last_monday = monday - timedelta(weeks=1)

        this_week = self._repo.get_daily_summaries(monday, 7)
        last_week = self._repo.get_daily_summaries(last_monday, 7)

        names = [(monday + timedelta(days=i)).strftime("%a") for i in range(7)]
        data = []
        this_total = 0
        last_total = 0
        for d in this_week:
            this_total += d["total_seconds"]
        for d in last_week:
            last_total += d["total_seconds"]

        # 两周并列显示：name 用 this_week / last_week 区分
        for i in range(7):
            tw = this_week[i]["total_seconds"]
            lw = last_week[i]["total_seconds"]
            data.append((f"{names[i]} 本周", tw, _BAR_COLORS[i % 8], None))
            data.append((f"{names[i]} 上周", lw, "#3a3a50", None))

        self._compare_chart.set_data(data)
        diff = this_total - last_total
        diff_str = f"+{diff // 60}m" if diff >= 0 else f"{diff // 60}m"
        self._compare_label.setText(f"本周: {this_total // 60}m  上周: {last_total // 60}m  ({diff_str})")

    def _shift_week(self, delta: int):
        self._week_offset += delta
        self._update_week_view()

    def _shift_month(self, delta: int):
        self._month_offset += delta
        self._update_month_view()
