"""仪表盘页面 —— 今日概览."""

from datetime import date
from typing import Optional

from PyQt6.QtCore import QTimer, Qt  # type: ignore
from PyQt6.QtGui import QColor  # type: ignore
from PyQt6.QtWidgets import (  # type: ignore
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QScrollArea, QVBoxLayout, QWidget,
)

from pulse.core.tracker import AppTracker
from pulse.db.repository import Repository
from pulse.utils.constants import DEFAULT_CATEGORIES

CATEGORY_COLORS = [
    "#4CAF50", "#2196F3", "#FF9800", "#E91E63",
    "#9C27B0", "#00BCD4", "#607D8B", "#9E9E9E",
]


class DashboardPage(QWidget):
    """仪表盘 —— 显示今日追踪概要."""

    def __init__(self, tracker: Optional[AppTracker] = None, repo: Optional[Repository] = None):
        super().__init__()
        self._tracker = tracker
        self._repo = repo

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(16)

        self._build_header()
        self._build_stats_row()
        self._build_section_label("分类分布")
        self._build_category_section()
        self._build_section_label("Top 应用")
        self._build_app_list()

        # 定时刷新
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(5000)

    def set_tracker(self, tracker: AppTracker) -> None:
        self._tracker = tracker

    # ── 构建子组件 ──────────────────────────────────────────

    def _build_header(self):
        self._page_title = QLabel("仪表盘")
        self._page_title.setObjectName("pageTitle")
        self._page_subtitle = QLabel("正在追踪...")
        self._page_subtitle.setObjectName("pageSubtitle")
        header = QVBoxLayout()
        header.setSpacing(4)
        header.addWidget(self._page_title)
        header.addWidget(self._page_subtitle)
        self._layout.addLayout(header)

    def _build_stats_row(self):
        row = QHBoxLayout()
        row.setSpacing(16)
        self._time_card = self._make_stat_card("今日活跃时长", "--")
        self._apps_card = self._make_stat_card("使用应用数", "--")
        self._session_card = self._make_stat_card("当前会话", "--")
        row.addWidget(self._time_card)
        row.addWidget(self._apps_card)
        row.addWidget(self._session_card)
        self._layout.addLayout(row)

    def _build_section_label(self, text: str):
        label = QLabel(text)
        label.setObjectName("sectionLabel")
        label.setStyleSheet("font-size: 15px; font-weight: 600; margin-top: 8px;")
        self._layout.addWidget(label)

    def _build_category_section(self):
        """分类分布区域 —— 彩色横条."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        container.setObjectName("card")
        self._cat_layout = QVBoxLayout(container)
        self._cat_layout.setSpacing(8)
        self._cat_layout.setContentsMargins(16, 16, 16, 16)

        # 占位
        self._cat_placeholder = QLabel("暂无分类数据（等待 LLM 分类）")
        self._cat_placeholder.setStyleSheet("color: #808098; font-size: 12px;")
        self._cat_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cat_layout.addWidget(self._cat_placeholder)

        self._cat_widgets = []  # (bar_fill, label) 用于更新
        scroll.setWidget(container)
        self._layout.addWidget(scroll, stretch=1)

    def _build_app_list(self):
        self._app_list = QListWidget()
        self._app_list.setObjectName("appList")
        self._app_list.setMaximumHeight(240)
        self._app_list.setFrameShape(QFrame.Shape.NoFrame)
        self._app_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._layout.addWidget(self._app_list)

    # ── 辅助 ────────────────────────────────────────────────

    @staticmethod
    def _make_stat_card(title: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setFixedHeight(100)
        layout = QVBoxLayout(card)
        layout.setSpacing(4)
        t = QLabel(title)
        t.setObjectName("cardTitle")
        v = QLabel(value)
        v.setObjectName("cardValue")
        v.setObjectName(f"cardValue_{title}")
        layout.addWidget(t)
        layout.addWidget(v, alignment=Qt.AlignmentFlag.AlignLeft)
        return card

    # ── 刷新数据 ────────────────────────────────────────────

    def _refresh(self):
        """从 tracker 和 repo 拉取最新数据刷新 UI."""
        today = date.today()
        total_sec = 0
        top_apps = []

        if self._repo:
            try:
                total_sec = self._repo.get_total_duration_by_date(today)
                top_apps = self._repo.get_usage_summary_by_date(today, "process_name")
            except Exception:
                pass

        self._update_stats(total_sec, top_apps)
        self._update_app_list(top_apps)
        self._update_session()

    def _update_stats(self, total_sec: int, top_apps: list):
        hours = total_sec // 3600
        mins = (total_sec % 3600) // 60
        time_text = f"{hours} 时 {mins} 分" if hours else f"{mins} 分"
        self._set_card_value("今日活跃时长", time_text)
        self._set_card_value("使用应用数", str(len(top_apps)))
        self._page_subtitle.setText(f"共追踪 {len(top_apps)} 个应用")

    def _update_app_list(self, top_apps: list):
        self._app_list.clear()
        if not top_apps:
            item = QListWidgetItem("暂无数据，请在后台运行 Pulse")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self._app_list.addItem(item)
            return
        for i, app in enumerate(top_apps[:10], 1):
            name = app["name"]
            secs = app["total_seconds"]
            h = secs // 3600
            m = (secs % 3600) // 60
            s = secs % 60
            if h:
                time_str = f"{h}h {m}m"
            elif m:
                time_str = f"{m}m {s}s"
            else:
                time_str = f"{s}s"
            text = f"  {i}.  {name:<30}  {time_str:>8}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, name)
            self._app_list.addItem(item)

    def _update_session(self):
        if self._tracker and self._tracker.current_session:
            cur = self._tracker.current_session
            session_text = f"{cur.process_name} ({cur.duration_seconds}s)"
        else:
            session_text = "---"
        self._set_card_value("当前会话", session_text)

    def _set_card_value(self, title: str, value: str):
        """根据 card title 找到对应的 value label 并更新."""
        # 遍历所有 card 的子孙控件
        for card in self.findChildren(QFrame, "card"):
            for child in card.findChildren(QLabel):
                if child.objectName() == f"cardValue_{title}":
                    child.setText(value)
                    return
