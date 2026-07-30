"""设置页面 —— 主题 / 追踪 / 自启 / 数据清理 / LLM."""

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QSpinBox, QVBoxLayout, QWidget,
)

from pulse.db.repository import Repository
from pulse.ui.theme import ThemeManager, ThemeMode
from pulse.utils.auto_start import is_auto_start_enabled, set_auto_start
from pulse.utils.config import ConfigManager


class StyledCombo(QComboBox):
    """QComboBox 子类 —— 弹出时强制注入暗色样式."""

    def showPopup(self):
        self.view().window().setStyleSheet("""
            QAbstractItemView {
                background-color: #000000;
                color: #ffffff;
                border: 1px solid #5a5a7a;
                outline: none;
            }
            QAbstractItemView::item {
                padding: 6px 10px;
                color: #ffffff;
            }
            QAbstractItemView::item:selected {
                background-color: #7c5cfc;
                color: #ffffff;
            }
        """)
        super().showPopup()


class SettingsPage(QWidget):
    """设置页面."""

    def __init__(self, config_mgr: ConfigManager, repo: Optional[Repository] = None):
        super().__init__()
        self._config_mgr = config_mgr
        self._repo = repo

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        self._layout = QVBoxLayout(container)
        self._layout.setSpacing(16)

        self._build_header()
        self._build_theme_section()
        self._build_tracker_section()
        self._build_llm_section()
        self._build_auto_start_section()
        self._build_cleanup_section()
        self._build_about_section()
        self._layout.addStretch()

        scroll.setWidget(container)
        root.addWidget(scroll)

    def set_repo(self, repo: Repository) -> None:
        self._repo = repo

    # ── 构建 ────────────────────────────────────────────

    def _build_header(self):
        title = QLabel("设置")
        title.setObjectName("pageTitle")
        self._layout.addWidget(title)

    def _build_theme_section(self):
        self._add_section("外观")
        self._theme_selector = self._add_combo("主题模式", ["跟随系统", "暗色", "亮色"])
        self._theme_selector.currentIndexChanged.connect(self._on_theme_changed)
        idx = {"system": 0, "dark": 1, "light": 2}.get(self._config_mgr.config.theme, 0)
        self._theme_selector.setCurrentIndex(idx)

    def _build_tracker_section(self):
        self._add_section("追踪")
        self._poll_spin = self._add_spin("轮询间隔（秒）", 1, 30, self._config_mgr.config.tracker.poll_interval)
        self._idle_spin = self._add_spin("空闲阈值（秒）", 30, 3600, self._config_mgr.config.tracker.idle_threshold)

    def _build_llm_section(self):
        self._add_section("AI 分类")

        row1 = QHBoxLayout()
        lbl1 = QLabel("API Key")
        lbl1.setFixedWidth(140)
        self._llm_key_input = QLineEdit()
        self._llm_key_input.setPlaceholderText("sk-... （留空则不启用）")
        self._llm_key_input.setFixedWidth(300)
        # QLineEdit 样式由全局 QSS 统一管理
        self._llm_key_input.setText(self._config_mgr.config.llm.api_key)
        row1.addWidget(lbl1)
        row1.addWidget(self._llm_key_input)
        row1.addStretch()
        self._layout.addLayout(row1)

        row2 = QHBoxLayout()
        lbl2 = QLabel("模型")
        lbl2.setFixedWidth(140)
        self._llm_model = StyledCombo()
        self._llm_model.addItems(["deepseek-chat", "deepseek-reasoner", "gpt-4o-mini", "gpt-4o"])
        self._llm_model.setCurrentText(self._config_mgr.config.llm.model or "deepseek-chat")
        self._llm_model.setFixedWidth(200)
        row2.addWidget(lbl2)
        row2.addWidget(self._llm_model)
        row2.addStretch()
        self._layout.addLayout(row2)

        self._llm_save_btn = QPushButton("保存 API 配置")
        self._llm_save_btn.setStyleSheet(
            "QPushButton { background: #7c5cfc; border: none; border-radius: 4px; "
            "padding: 8px 20px; color: #fff; font-weight: 600; }"
            "QPushButton:hover { background: #6a4acc; }"
        )
        self._llm_save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._llm_save_btn.setFixedWidth(200)
        self._llm_save_btn.clicked.connect(self._save_llm_config)
        self._layout.addWidget(self._llm_save_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        info = QLabel("配置后将在分类页面提供「AI 自动分类」功能，基于 DeepSeek API")
        info.setStyleSheet("color: #606080; font-size: 11px;")
        self._layout.addWidget(info)

    def _build_auto_start_section(self):
        self._add_section("开机自启")
        self._auto_start_cb = QCheckBox("开机时自动启动 Pulse")
        self._auto_start_cb.setChecked(is_auto_start_enabled())
        self._auto_start_cb.toggled.connect(self._on_auto_start_toggled)
        self._layout.addWidget(self._auto_start_cb)

    def _build_cleanup_section(self):
        self._add_section("数据清理")
        row = QHBoxLayout()
        lbl = QLabel("保留时长")
        lbl.setFixedWidth(140)
        self._cleanup_spin = QSpinBox()
        self._cleanup_spin.setRange(1, 60)
        self._cleanup_spin.setValue(6)
        self._cleanup_spin.setSuffix(" 个月")
        self._cleanup_spin.setFixedWidth(150)
        # QSpinBox 样式由全局 QSS 统一管理

        self._cleanup_btn = QPushButton("立即清理")
        self._cleanup_btn.setStyleSheet(
            "QPushButton { background: #f44336; border: none; border-radius: 4px; "
            "padding: 8px 20px; color: #fff; font-weight: 600; }"
            "QPushButton:hover { background: #d32f2f; }"
        )
        self._cleanup_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cleanup_btn.clicked.connect(self._do_cleanup)

        row.addWidget(lbl)
        row.addWidget(self._cleanup_spin)
        row.addWidget(self._cleanup_btn)
        row.addStretch()
        self._layout.addLayout(row)

        self._cleanup_info = QLabel("当前未执行过清理")
        self._cleanup_info.setStyleSheet("color: #606080; font-size: 11px;")
        self._layout.addWidget(self._cleanup_info)

    def _build_about_section(self):
        self._add_section("关于")
        about = QLabel("Pulse v0.1.0\n个性化智能桌面行为分析助手\n数据存储于本地 SQLite")
        about.setStyleSheet("color: #808098; line-height: 1.6;")
        about.setWordWrap(True)
        self._layout.addWidget(about)

    # ── 辅助 ────────────────────────────────────────────

    def _add_section(self, title: str):
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFixedHeight(1)
        self._layout.addWidget(sep)
        label = QLabel(title)
        label.setStyleSheet("font-size: 15px; font-weight: 600; margin-top: 4px;")
        self._layout.addWidget(label)

    def _add_combo(self, label: str, items: list) -> QComboBox:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(140)
        combo = StyledCombo()
        combo.addItems(items)
        combo.setFixedWidth(200)
        row.addWidget(lbl)
        row.addWidget(combo)
        row.addStretch()
        self._layout.addLayout(row)
        return combo

    def _add_spin(self, label: str, min_v: int, max_v: int, default_v) -> QSpinBox:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(140)
        spin = QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setValue(int(default_v))
        spin.setFixedWidth(200)
        row.addWidget(lbl)
        row.addWidget(spin)
        row.addStretch()
        self._layout.addLayout(row)
        return spin

    # ── 逻辑 ────────────────────────────────────────────

    def _on_theme_changed(self, idx: int):
        mapping = {0: ThemeMode.SYSTEM, 1: ThemeMode.DARK, 2: ThemeMode.LIGHT}
        mode = mapping.get(idx, ThemeMode.SYSTEM)
        ThemeManager.instance().set_mode(mode)
        cfg = self._config_mgr.config
        cfg.theme = mode.value
        self._config_mgr.save()

    def _on_auto_start_toggled(self, enabled: bool):
        set_auto_start(enabled)
        cfg = self._config_mgr.config
        cfg.auto_start = enabled
        self._config_mgr.save()

    def _save_llm_config(self):
        cfg = self._config_mgr.config
        cfg.llm.api_key = self._llm_key_input.text().strip()
        cfg.llm.model = self._llm_model.currentText()
        cfg.llm.enabled = bool(cfg.llm.api_key)
        self._config_mgr.save()
        self._llm_save_btn.setText("已保存 ✓")
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: self._llm_save_btn.setText("保存 API 配置"))

    def _do_cleanup(self):
        if not self._repo:
            return
        months = self._cleanup_spin.value()
        reply = QMessageBox.question(
            self, "确认清理",
            f"确定要删除 {months} 个月之前的所有使用记录吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            count = self._repo.cleanup_by_months(months)
            self._cleanup_info.setText(f"已清理 {count} 条 {months} 个月前的记录")
        except Exception as e:
            self._cleanup_info.setText(f"清理失败: {e}")
