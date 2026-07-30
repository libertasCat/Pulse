"""应用图标缓存 —— 从 exe 提取图标，供柱状图使用."""

import logging
import os
from pathlib import Path
from typing import Optional

from PyQt6.QtGui import QIcon, QPixmap

from pulse.utils.constants import DATA_DIR

logger = logging.getLogger(__name__)

_ICON_DIR = DATA_DIR / "icons"
_FALLBACK_ICON: Optional[QIcon] = None
_PIXMAP_CACHE: dict[str, QIcon] = {}


def _ensure_icon_dir():
    _ICON_DIR.mkdir(parents=True, exist_ok=True)


def _make_fallback() -> QIcon:
    """生成一个默认的应用图标（纯色方块 + 字母）. """
    global _FALLBACK_ICON
    if _FALLBACK_ICON is None:
        from PyQt6.QtCore import QSize, Qt
        from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
        pm = QPixmap(32, 32)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#4a4a6a"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, 32, 32, 6, 6)
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "A")
        painter.end()
        _FALLBACK_ICON = QIcon(pm)
    return _FALLBACK_ICON


def _extract_exe_icon(exe_path: str) -> Optional[QPixmap]:
    """从 exe 文件提取 32x32 图标."""
    try:
        import win32gui
        import win32api
        large, small = win32gui.ExtractIconExW(exe_path, 0, 1, 1)
        if small and small[0]:
            # 从 HICON 转为 QPixmap
            from PyQt6.QtGui import QPixmap
            import ctypes
            pm = QPixmap.fromWinHICON(small[0])
            win32gui.DestroyIcon(small[0])
            if large and large[0]:
                win32gui.DestroyIcon(large[0])
            if pm and not pm.isNull():
                return pm
    except Exception:
        pass
    return None


def get_app_icon(process_name: str, exe_path: Optional[str] = None) -> QIcon:
    """获取应用图标（缓存命中则直接返回）. """
    if process_name in _PIXMAP_CACHE:
        return _PIXMAP_CACHE[process_name]

    pm = None

    # 方法1: 从 exe 直接提取
    if exe_path and os.path.isfile(exe_path):
        pm = _extract_exe_icon(exe_path)
        if pm:
            # 缓存到磁盘
            _ensure_icon_dir()
            cached = _ICON_DIR / f"{process_name.replace('.', '_')}.png"
            pm.save(str(cached), "PNG")

    # 方法2: 从缓存文件加载
    if pm is None:
        _ensure_icon_dir()
        cached = _ICON_DIR / f"{process_name.replace('.', '_')}.png"
        if cached.exists():
            from PyQt6.QtGui import QPixmap
            pm = QPixmap(str(cached))

    # 方法3: 兜底
    if pm is None:
        icon = _make_fallback()
    else:
        icon = QIcon(pm)

    _PIXMAP_CACHE[process_name] = icon
    return icon


def cache_icon_from_exe(process_name: str, exe_path: str) -> Optional[Path]:
    """提取并缓存 exe 图标到磁盘."""
    pm = _extract_exe_icon(exe_path)
    if pm is None:
        return None
    _ensure_icon_dir()
    dest = _ICON_DIR / f"{process_name.replace('.', '_')}.png"
    pm.save(str(dest), "PNG")
    logger.debug("图标已缓存: %s → %s", process_name, dest)
    return dest


_APP_ICON: Optional[QIcon] = None


def get_pulse_icon() -> QIcon:
    """生成 / 返回 Pulse 应用图标（紫色 P 字）. """
    global _APP_ICON
    if _APP_ICON is None:
        from PyQt6.QtCore import QSize, Qt
        from PyQt6.QtGui import QColor, QFont, QGradient, QLinearGradient, QPainter, QPixmap
        pm = QPixmap(64, 64)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 渐变背景
        grad = QLinearGradient(0, 0, 64, 64)
        grad.setColorAt(0.0, QColor("#7c5cfc"))
        grad.setColorAt(1.0, QColor("#5a3cfc"))
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(4, 4, 56, 56, 12, 12)

        # P 字母
        painter.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI", 32, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pm.rect().adjusted(0, -2, 0, 0),
                         Qt.AlignmentFlag.AlignCenter, "P")
        painter.end()

        _APP_ICON = QIcon(pm)
    return _APP_ICON
