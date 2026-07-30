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
    border-radius: 10px;
    border: 1px solid #3a3a50;
    padding: 14px;
}
QFrame#card:hover {
    border-color: #5a5a7a;
}
QFrame#card QFrame#card {
    background-color: #1e1e34;
    border-color: #2a2a44;
}
QLabel#cardTitle {
    color: #808098;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.2px;
}
QLabel#cardValue {
    color: #ffffff;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.5px;
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

/* ── ComboBox / SpinBox / LineEdit ── */
QComboBox, QSpinBox, QLineEdit {
    background-color: #000000;
    color: #ffffff;
    border: 1px solid #6a6a8a;
    border-radius: 4px;
    padding: 4px 10px;
    min-height: 28px;
}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover {
    border-color: #7c5cfc;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox::placeholder, QLineEdit::placeholder {
    color: #606080;
}

/* ── 下拉列表（全局，因为弹出层不在母控件树内） ── */
QAbstractItemView {
    background-color: #000000;
    color: #ffffff;
    outline: none;
    selection-background-color: #7c5cfc;
}
QAbstractItemView::item {
    padding: 6px 10px;
    color: #ffffff;
}
QAbstractItemView::item:hover {
    background-color: #3a3a5a;
}
QAbstractItemView::item:selected {
    background-color: #7c5cfc;
}
QAbstractItemView QScrollBar:vertical {
    background: transparent;
    width: 6px;
}
QAbstractItemView QScrollBar::handle:vertical {
    background: #4a4a6a;
    border-radius: 3px;
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

/* ── 右键菜单 ── */
QMenu {
    background-color: #25253a;
    border: 1px solid #3a3a50;
    border-radius: 8px;
    padding: 6px 0;
}
QMenu::item {
    padding: 8px 28px 8px 20px;
    color: #ffffff;
    font-size: 13px;
}
QMenu::item:selected {
    background-color: #7c5cfc;
    color: #ffffff;
}
QMenu::item:disabled {
    color: #606080;
}
QMenu::separator {
    height: 1px;
    background: #3a3a50;
    margin: 4px 12px;
}

/* ── 复选框 ── */
QCheckBox {
    color: #e0e0e8;
    spacing: 10px;
    font-size: 13px;
}

QColorDialog {
    background-color: #25253a;
    color: #ffffff;
}
QColorDialog QLabel, QColorDialog QSpinBox, QColorDialog QComboBox {
    color: #ffffff;
    background-color: #1e1e34;
}
QColorDialog QPushButton {
    background-color: #7c5cfc;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
    min-height: 24px;
}
QColorDialog QPushButton:hover {
    background-color: #6a4acc;
}
QColorDialog QPushButton#cancelButton {
    background-color: #4a4a6a;
    color: #ffffff;
}
QFileDialog {
    background-color: #25253a;
    color: #ffffff;
}
QFileDialog QLabel, QFileDialog QComboBox, QFileDialog QLineEdit, QFileDialog QTreeView {
    color: #ffffff;
    background-color: #1e1e34;
}
QFileDialog QPushButton {
    background-color: #7c5cfc;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
}
QFileDialog QPushButton:hover {
    background-color: #6a4acc;
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
    border-radius: 10px;
    border: 1px solid #e0e0e8;
    padding: 14px;
}
QFrame#card:hover {
    border-color: #c0c0d0;
}
QFrame#card QFrame#card {
    background-color: #f8f8fc;
    border-color: #e8e8f0;
}
QLabel#cardTitle {
    color: #808098;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.2px;
}
QLabel#cardValue {
    color: #1a1a2e;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: -0.5px;
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

/* ── ComboBox / SpinBox / LineEdit ── */
QComboBox, QSpinBox, QLineEdit {
    background-color: #ffffff;
    color: #1a1a2e;
    border: 1px solid #c0c0d0;
    border-radius: 4px;
    padding: 4px 10px;
    min-height: 28px;
}
QComboBox:hover, QSpinBox:hover, QLineEdit:hover {
    border-color: #7c5cfc;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox::placeholder, QLineEdit::placeholder {
    color: #b0b0b8;
}

/* ── 下拉列表（全局） ── */
QAbstractItemView {
    background-color: #ffffff;
    color: #1a1a2e;
    outline: none;
    selection-background-color: #ede5ff;
}
QAbstractItemView::item {
    padding: 6px 10px;
    color: #1a1a2e;
}
QAbstractItemView::item:hover {
    background-color: #f5f0ff;
}
QAbstractItemView::item:selected {
    background-color: #ede5ff;
}
QAbstractItemView QScrollBar:vertical {
    background: transparent;
    width: 6px;
}
QAbstractItemView QScrollBar::handle:vertical {
    background: #d0d0d8;
    border-radius: 3px;
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

/* ── 右键菜单 ── */
QMenu {
    background-color: #ffffff;
    border: 1px solid #e0e0e8;
    border-radius: 8px;
    padding: 6px 0;
}
QMenu::item {
    padding: 8px 28px 8px 20px;
    color: #1a1a2e;
    font-size: 13px;
}
QMenu::item:selected {
    background-color: #f0ecff;
    color: #7c5cfc;
}
QMenu::separator {
    height: 1px;
    background: #e0e0e8;
    margin: 4px 12px;
}

/* ── 复选框 ── */
QCheckBox {
    color: #1a1a2e;
    spacing: 10px;
    font-size: 13px;
}

QColorDialog {
    background-color: #f5f5f8;
    color: #1a1a2e;
}
QColorDialog QPushButton {
    background-color: #7c5cfc;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
}
QFileDialog {
    background-color: #f5f5f8;
    color: #1a1a2e;
}
QFileDialog QPushButton {
    background-color: #7c5cfc;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 16px;
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
        """将当前主题应用到 QApplication（QSS + Palette）. """
        app = QApplication.instance()
        if app is None:
            return
        qss = self._resolve_qss()
        app.setStyleSheet(qss)
        app.setPalette(self._build_palette())
        logger.info("主题已应用: %s", self.current_name)

    def _build_palette(self) -> QPalette:
        """构建与当前主题匹配的 QPalette."""
        mode = self._resolved_mode()
        pal = QPalette()
        if mode == ThemeMode.DARK:
            pal.setColor(QPalette.ColorRole.Window, QColor("#000000"))
            pal.setColor(QPalette.ColorRole.WindowText, QColor("#ffffff"))
            pal.setColor(QPalette.ColorRole.Button, QColor("#000000"))
            pal.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
            pal.setColor(QPalette.ColorRole.Text, QColor("#ffffff"))
            pal.setColor(QPalette.ColorRole.Base, QColor("#000000"))
            pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#1a1a2e"))
        else:
            pal.setColor(QPalette.ColorRole.Window, QColor("#ffffff"))
            pal.setColor(QPalette.ColorRole.WindowText, QColor("#1a1a2e"))
            pal.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
            pal.setColor(QPalette.ColorRole.ButtonText, QColor("#1a1a2e"))
            pal.setColor(QPalette.ColorRole.Text, QColor("#1a1a2e"))
            pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
            pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#f5f5f8"))
        return pal

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
