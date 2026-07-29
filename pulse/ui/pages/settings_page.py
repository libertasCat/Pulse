"""设置页面 —— 主题切换 / 追踪配置."""

from PyQt6.QtCore import Qt  # type: ignore
from PyQt6.QtWidgets import (  # type: ignore
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QVBoxLayout, QWidget,
)

from pulse.ui.theme import ThemeManager, ThemeMode
from pulse.utils.config import ConfigManager


class SettingsPage(QWidget):
    """设置页面."""

    def __init__(self, config_mgr: ConfigManager):
        super().__init__()
        self._config_mgr = config_mgr

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题
        title = QLabel("设置")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # ── 外观 ──
        self._add_section(layout, "外观")
        self._theme_selector = self._add_combo_row(
            layout, "主题模式", ["跟随系统", "暗色", "亮色"]
        )
        self._theme_selector.currentIndexChanged.connect(self._on_theme_changed)
        idx = self._theme_idx(self._config_mgr.config.theme)
        self._theme_selector.setCurrentIndex(idx)

        # ── 追踪 ──
        self._add_section(layout, "追踪")
        self._poll_spin = self._add_spin_row(
            layout, "轮询间隔（秒）", 1, 30, int(self._config_mgr.config.tracker.poll_interval)
        )
        self._idle_spin = self._add_spin_row(
            layout, "空闲阈值（秒）", 30, 3600, self._config_mgr.config.tracker.idle_threshold
        )

        # ── 关于 ──
        self._add_section(layout, "关于")
        about = QLabel("Pulse v0.1.0\n个性化智能桌面行为分析助手\n数据存储于本地 SQLite")
        about.setStyleSheet("color: #808098; line-height: 1.6;")
        about.setWordWrap(True)
        layout.addWidget(about)

        layout.addStretch()

    # ── 构建辅助 ──────────────────────────────────────────

    @staticmethod
    def _add_section(layout: QVBoxLayout, title: str):
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFixedHeight(1)
        layout.addWidget(sep)
        label = QLabel(title)
        label.setStyleSheet("font-size: 15px; font-weight: 600; margin-top: 4px;")
        layout.addWidget(label)

    @staticmethod
    def _add_combo_row(layout: QVBoxLayout, label: str, items: list) -> QComboBox:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(140)
        combo = QComboBox()
        combo.addItems(items)
        combo.setFixedWidth(200)
        row.addWidget(lbl)
        row.addWidget(combo)
        row.addStretch()
        layout.addLayout(row)
        return combo

    @staticmethod
    def _add_spin_row(layout: QVBoxLayout, label: str, min_v: int, max_v: int, default_v: int) -> QSpinBox:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(140)
        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setValue(default_v)
        spin.setFixedWidth(200)
        row.addWidget(lbl)
        row.addWidget(spin)
        row.addStretch()
        layout.addLayout(row)
        return spin

    # ── 逻辑 ──────────────────────────────────────────────

    @staticmethod
    def _theme_idx(mode: str) -> int:
        mapping = {"system": 0, "dark": 1, "light": 2}
        return mapping.get(mode, 0)

    def _on_theme_changed(self, idx: int):
        mapping = {0: ThemeMode.SYSTEM, 1: ThemeMode.DARK, 2: ThemeMode.LIGHT}
        mode = mapping.get(idx, ThemeMode.SYSTEM)
        ThemeManager.instance().set_mode(mode)
        # 持久化
        cfg = self._config_mgr.config
        cfg.theme = mode.value
        self._config_mgr.save()
