"""系统托盘图标."""

import logging
from typing import Optional

from PyQt6.QtCore import Qt  # type: ignore
from PyQt6.QtGui import QAction, QIcon  # type: ignore
from PyQt6.QtWidgets import (  # type: ignore
    QApplication, QMenu, QSystemTrayIcon, QWidget,
)

logger = logging.getLogger(__name__)


class TrayIcon(QSystemTrayIcon):
    """系统托盘 —— 右键菜单 + 双击恢复窗口."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._parent = parent

        # 使用内置图标（后续可替换为自定义 .ico/.png）
        self.setIcon(QApplication.style().standardIcon(
            QApplication.style().StandardPixmap.SP_ComputerIcon
        ))
        self.setToolTip("Pulse — 应用追踪中")

        self._build_menu()
        self.activated.connect(self._on_activated)

        self._paused = False

    @property
    def is_visible(self) -> bool:
        return self.isVisible()

    def _build_menu(self):
        menu = QMenu()

        self._show_action = QAction("显示主窗口", self)
        self._show_action.triggered.connect(self._show_window)
        menu.addAction(self._show_action)

        menu.addSeparator()

        self._pause_action = QAction("暂停追踪", self)
        self._pause_action.triggered.connect(self._toggle_pause)
        menu.addAction(self._pause_action)

        menu.addSeparator()

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        self.setContextMenu(menu)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_window(self):
        if self._parent:
            self._parent.show_from_tray()

    def _toggle_pause(self):
        self._paused = not self._paused
        if self._paused:
            self._pause_action.setText("恢复追踪")
            self.setToolTip("Pulse — 已暂停")
        else:
            self._pause_action.setText("暂停追踪")
            self.setToolTip("Pulse — 应用追踪中")

    @staticmethod
    def _quit_app():
        QApplication.quit()

    def show(self):
        super().show()
        logger.info("系统托盘已显示")
