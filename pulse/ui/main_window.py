"""主窗口 —— 侧边导航 + 页面切换."""

from typing import Optional

from PyQt6.QtCore import Qt, QTimer  # type: ignore
from PyQt6.QtGui import QAction, QIcon  # type: ignore
from PyQt6.QtWidgets import (  # type: ignore
    QButtonGroup, QHBoxLayout, QMainWindow, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)

from pulse.core.tracker import AppTracker
from pulse.db.repository import Repository
from pulse.ui.pages.dashboard_page import DashboardPage
from pulse.ui.pages.stats_page import StatsPage
from pulse.ui.pages.category_page import CategoryPage
from pulse.ui.pages.calendar_page import CalendarPage
from pulse.ui.pages.settings_page import SettingsPage
from pulse.utils.icon_cache import get_pulse_icon
from pulse.ui.tray_icon import TrayIcon
from pulse.utils.config import ConfigManager


class MainWindow(QMainWindow):
    """Pulse 主窗口."""

    def __init__(
        self,
        tracker: Optional[AppTracker] = None,
        repo: Optional[Repository] = None,
        config_mgr: Optional[ConfigManager] = None,
    ):
        super().__init__()
        self._tracker = tracker
        self._repo = repo
        self._config_mgr = config_mgr or ConfigManager()
        self._tray: Optional[TrayIcon] = None

        self.setWindowTitle("Pulse")
        self.setWindowIcon(get_pulse_icon())
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)

        self._setup_ui()

    def set_tracker(self, tracker: AppTracker) -> None:
        self._tracker = tracker
        self._dashboard.set_tracker(tracker)

    def set_repo(self, repo: Repository) -> None:
        self._repo = repo
        self._stats.set_repo(repo)
        self._calendar.set_repo(repo)
        self._settings.set_repo(repo)

    def _setup_ui(self):
        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── 侧边导航 ──
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(68)
        nav_layout = QVBoxLayout(sidebar)
        nav_layout.setContentsMargins(0, 12, 0, 12)
        nav_layout.setSpacing(2)

        # logo / 标题
        logo = QPushButton("P")
        logo.setFixedHeight(40)
        logo.setStyleSheet(
            "font-size: 20px; font-weight: 800; color: #7c5cfc; "
            "background: transparent; border: none;"
        )
        logo.setEnabled(False)
        nav_layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)
        nav_layout.addSpacing(12)

        # 导航按钮组
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_group.idClicked.connect(self._switch_page)

        nav_items = [
            (0, "📊", "仪表盘"),
            (1, "📈", "统计"),
            (2, "📁", "分类"),
            (3, "📅", "日历"),
            (4, "⚙️", "设置"),
        ]

        for btn_id, icon, text in nav_items:
            btn = QPushButton(f"{icon}\n{text}")
            btn.setObjectName("navBtn")
            btn.setCheckable(True)
            btn.setFixedSize(64, 64)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._nav_group.addButton(btn, btn_id)
            nav_layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        nav_layout.addStretch()

        # ── 内容区 ──
        self._stack = QStackedWidget()
        self._stack.setObjectName("contentStack")

        # 页面
        self._dashboard = DashboardPage(self._tracker, self._repo, self._config_mgr)
        self._stats = StatsPage(self._repo)
        self._category = CategoryPage(self._repo, self._config_mgr)
        self._calendar = CalendarPage(self._repo)
        self._settings = SettingsPage(self._config_mgr, self._repo)

        self._stack.addWidget(self._dashboard)   # index 0
        self._stack.addWidget(self._stats)        # index 1
        self._stack.addWidget(self._category)     # index 2
        self._stack.addWidget(self._calendar)     # index 3
        self._stack.addWidget(self._settings)     # index 4

        root_layout.addWidget(sidebar)
        root_layout.addWidget(self._stack, stretch=1)

        # 默认选中仪表盘
        nav_btns = self._nav_group.buttons()
        if nav_btns:
            nav_btns[0].setChecked(True)

    @staticmethod
    def _make_placeholder(text: str) -> QWidget:
        w = QWidget()
        from PyQt6.QtWidgets import QLabel
        layout = QVBoxLayout(w)
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #808098; font-size: 18px;")
        layout.addWidget(label)
        return w

    def _switch_page(self, btn_id: int):
        self._stack.setCurrentIndex(btn_id)

    # ── 系统托盘 ──────────────────────────────────────────

    def set_tray_icon(self, tray: TrayIcon) -> None:
        self._tray = tray

    def closeEvent(self, event):
        """关闭按钮 → 最小化到托盘."""
        if self._tray and self._tray.is_visible:
            self.hide()
            event.ignore()
        else:
            event.accept()

    # ── 窗口管理 ──────────────────────────────────────────

    def show_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()
