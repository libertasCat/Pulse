"""主题管理 —— 暗色 / 亮色 / 跟随系统."""

import logging
import platform
from enum import Enum
from typing import Optional

from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtWidgets import QApplication

logger = logging.getLogger(__name__)


class ThemeMode(Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


DARK_QSS = """
/* ── 全局 ── */
QMainWindow, QWidget#centralWidget {
    background-color: #1a1a2e;
    color: #ffffff;
}
QWidget {
    background-color: transparent;
    color: #ffffff;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

/* ── 侧边栏 ── */
QWidget#sidebar {
    background-color: #16162a;
    border-right: 1px solid #2a2a40;
}
QPushButton#navBtn {
    background-color: transparent;
    color: #808098;
    border: none;
    border-left: 3px solid transparent;
    padding: 10px 4px;
    text-align: center;
    font-size: 11px;
}
QPushButton#navBtn:hover {
    background-color: #1f1f38;
    color: #c0c0d0;
}
QPushButton#navBtn:checked {
    background-color: #25253a;
    color: #7c5cfc;
    border-left: 3px solid #7c5cfc;
}

/* ── 卡片 ── */
QFrame#card {
    background-color: #25253a;
    border-radius: 8px;
    border: 1px solid #3a3a50;
    padding: 12px;
}
QLabel#cardTitle {
    color: #a0a0b8;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QLabel#cardValue {
    color: #ffffff;
    font-size: 28px;
    font-weight: 700;
}

/* ── 分类横条 ── */
QFrame#catBar {
    background-color: #2d2d45;
    border-radius: 4px;
    min-height: 20px;
}
QFrame#catBarFill {
    border-radius: 4px;
    min-height: 20px;
}
QLabel#catLabel {
    color: #c0c0d0;
    font-size: 12px;
}

/* ── 应用列表 ── */
QListWidget, QListWidget#appList {
    background-color: transparent;
    border: none;
    outline: none;
}
QListWidget#appList::item {
    background-color: #1e1e34;
    border-radius: 6px;
    padding: 8px 12px;
    margin: 2px 0px;
    border: 1px solid #3a3a50;
    color: #ffffff;
}
QListWidget#appList::item:hover {
    background-color: #2a2a44;
    border-color: #4a4a68;
}

/* ── 标题 ── */
QLabel#pageTitle {
    color: #ffffff;
    font-size: 22px;
    font-weight: 700;
}
QLabel#pageSubtitle {
    color: #808098;
    font-size: 13px;
}

/* ── 分割线 ── */
QFrame#separator {
    background-color: #3a3a50;
    max-height: 1px;
}

/* ── ComboBox / SpinBox (设置页) ── */
QComboBox, QSpinBox {
    background-color: #1e1e34;
    color: #ffffff;
    border: 1px solid #3a3a50;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 28px;
}
QComboBox:hover, QSpinBox:hover {
    border-color: #7c5cfc;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #25253a;
    color: #ffffff;
    border: 1px solid #3a3a50;
    selection-background-color: #7c5cfc;
}

/* ── ScrollBar ── */
QScrollBar:vertical {
    background-color: #1a1a2e;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #3a3a50;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #5a5a70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


LIGHT_QSS = """
/* ── 全局 ── */
QMainWindow, QWidget#centralWidget {
    background-color: #f5f5f8;
    color: #1a1a2e;
}
QWidget {
    background-color: transparent;
    color: #1a1a2e;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}

/* ── 侧边栏 ── */
QWidget#sidebar {
    background-color: #ffffff;
    border-right: 1px solid #e0e0e8;
}
QPushButton#navBtn {
    background-color: transparent;
    color: #909098;
    border: none;
    border-left: 3px solid transparent;
    padding: 10px 4px;
    text-align: center;
    font-size: 11px;
}
QPushButton#navBtn:hover {
    background-color: #f0f0f5;
    color: #505060;
}
QPushButton#navBtn:checked {
    background-color: #f5f0ff;
    color: #7c5cfc;
    border-left: 3px solid #7c5cfc;
}

/* ── 卡片 ── */
QFrame#card {
    background-color: #ffffff;
    border-radius: 8px;
    border: 1px solid #e0e0e8;
    padding: 12px;
}
QLabel#cardTitle {
    color: #808098;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QLabel#cardValue {
    color: #1a1a2e;
    font-size: 28px;
    font-weight: 700;
}

/* ── 分类横条 ── */
QFrame#catBar {
    background-color: #e8e8f0;
    border-radius: 4px;
    min-height: 20px;
}
QFrame#catBarFill {
    border-radius: 4px;
    min-height: 20px;
}
QLabel#catLabel {
    color: #505060;
    font-size: 12px;
}

/* ── 应用列表 ── */
QListWidget, QListWidget#appList {
    background-color: transparent;
    border: none;
    outline: none;
}
QListWidget#appList::item {
    background-color: #ffffff;
    border-radius: 6px;
    padding: 8px 12px;
    margin: 2px 0px;
    border: 1px solid #e0e0e8;
    color: #1a1a2e;
}
QListWidget#appList::item:hover {
    background-color: #f8f8fc;
    border-color: #c0c0d0;
}

/* ── 标题 ── */
QLabel#pageTitle {
    color: #1a1a2e;
    font-size: 22px;
    font-weight: 700;
}
QLabel#pageSubtitle {
    color: #808098;
    font-size: 13px;
}

/* ── 分割线 ── */
QFrame#separator {
    background-color: #e0e0e8;
    max-height: 1px;
}

/* ── ComboBox / SpinBox ── */
QComboBox, QSpinBox {
    background-color: #ffffff;
    color: #1a1a2e;
    border: 1px solid #e0e0e8;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 28px;
}
QComboBox:hover, QSpinBox:hover {
    border-color: #7c5cfc;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1a1a2e;
    border: 1px solid #e0e0e8;
    selection-background-color: #ede5ff;
}

/* ── ScrollBar ── */
QScrollBar:vertical {
    background-color: #f5f5f8;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background-color: #d0d0d8;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background-color: #b0b0c0;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


class ThemeManager:
    """主题管理器 —— 应用 / 切换 / 检测系统主题."""

    _instance: Optional["ThemeManager"] = None

    def __init__(self):
        self._mode = ThemeMode.SYSTEM

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def mode(self) -> ThemeMode:
        return self._mode

    def set_mode(self, mode: ThemeMode) -> None:
        self._mode = mode
        self.apply()

    def apply(self) -> None:
        """将当前主题应用到 QApplication."""
        app = QApplication.instance()
        if app is None:
            return
        qss = self._resolve_qss()
        app.setStyleSheet(qss)
        logger.info("主题已应用: %s", self.current_name)

    @property
    def current_name(self) -> str:
        return self._resolved_mode().value

    def _resolve_qss(self) -> str:
        mode = self._resolved_mode()
        return DARK_QSS if mode == ThemeMode.DARK else LIGHT_QSS

    def _resolved_mode(self) -> ThemeMode:
        if self._mode == ThemeMode.SYSTEM:
            return ThemeMode.DARK if self._is_system_dark() else ThemeMode.LIGHT
        return self._mode

    @staticmethod
    def _is_system_dark() -> bool:
        """检测 Windows 系统是否为暗色模式."""
        if platform.system() != "Windows":
            return False
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return value == 0
        except (OSError, FileNotFoundError):
            return False
