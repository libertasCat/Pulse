"""分类管理页面 —— 网格卡片 / 图标选择 / 应用分配."""

import os
from typing import Optional

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QButtonGroup, QColorDialog, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from PyQt6.QtCore import QTimer

from datetime import date

from pulse.core.classifier import ClassifierService
from pulse.db.repository import Repository
from pulse.ui.theme import ThemeManager, ThemeMode
from pulse.utils.config import ConfigManager
from pulse.utils.icon_cache import get_app_icon
from pulse.utils.process_names import strip_ext

_PRESET_ICONS = [
    "💻", "🌐", "💬", "🎮", "📝", "🎵", "🎬", "📚",
    "🛠️", "⚙️", "🎨", "📷", "📊", "🔬", "🏠", "📦",
    "☁️", "🔒", "📞", "✉️", "📋", "🗂️", "⏰", "🔧",
]

_CATEGORY_COLORS = [
    "#7c5cfc", "#2196F3", "#4CAF50", "#FF9800", "#E91E63",
    "#00BCD4", "#9C27B0", "#FF5722", "#607D8B", "#795548",
]


class CategoryPage(QWidget):
    """分类管理页面."""

    def __init__(self, repo: Optional[Repository] = None, config_mgr: Optional[ConfigManager] = None):
        super().__init__()
        self._repo = repo
        self._config_mgr = config_mgr
        self._editing_cat_id: Optional[int] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # 标题
        title = QLabel("分类管理")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # 两栏布局
        split = QHBoxLayout()
        split.setSpacing(16)

        # ── 左栏：紧凑分类选择器（彩色图标按钮） ──
        left = QVBoxLayout()
        left_label = QLabel("选择分类")
        left_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        left.addWidget(left_label)

        self._cat_selector = QButtonGroup(self)
        self._cat_selector.setExclusive(True)
        self._cat_selector.idClicked.connect(self._select_category)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        self._cat_selector_container = QWidget()
        self._cat_selector_layout = QVBoxLayout(self._cat_selector_container)
        self._cat_selector_layout.setSpacing(4)
        scroll.setWidget(self._cat_selector_container)
        left.addWidget(scroll, stretch=1)

        add_btn = QPushButton("+ 新分类")
        add_btn.setStyleSheet(
            "QPushButton { background: #7c5cfc; border: none; border-radius: 6px; "
            "padding: 8px; color: #fff; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #6a4acc; }"
        )
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._start_new_category)
        left.addWidget(add_btn)

        self._ai_btn = QPushButton("🤖 分类")
        self._ai_btn.setStyleSheet(
            "QPushButton { background: #4a4a6a; border: none; border-radius: 6px; "
            "padding: 8px; color: #fff; font-size: 12px; font-weight: 600; }"
            "QPushButton:hover { background: #5a5a7a; }"
            "QPushButton:disabled { color: #606080; }"
        )
        self._ai_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_btn.clicked.connect(self._do_ai_classify)
        left.addWidget(self._ai_btn)

        split.addLayout(left, stretch=1)

        # ── 右栏：编辑面板（完整宽度） ──
        right = QVBoxLayout()
        right_label = QLabel("编辑分类")
        right_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        right.addWidget(right_label)

        self._edit_panel = QFrame()
        self._edit_panel.setObjectName("card")
        self._edit_panel.setVisible(False)
        ep = QVBoxLayout(self._edit_panel)
        ep.setSpacing(12)

        # 名称
        ep.addWidget(QLabel("名称"))
        self._edit_name = QLineEdit()
        self._edit_name.setPlaceholderText("分类名称")
        self._edit_name.setStyleSheet("padding: 6px; border-radius: 4px; background: #1e1e34; color: #fff; border: 1px solid #3a3a50;")
        ep.addWidget(self._edit_name)

        # 颜色
        ep.addWidget(QLabel("颜色"))
        color_row = QHBoxLayout()
        self._edit_color_btn = QPushButton()
        self._edit_color_btn.setFixedSize(40, 30)
        self._edit_color_btn.setStyleSheet("background: #7c5cfc; border-radius: 4px; border: none;")
        self._edit_color_btn.clicked.connect(self._pick_edit_color)
        color_row.addWidget(self._edit_color_btn)
        color_row.addStretch()
        ep.addLayout(color_row)

        # 图标选择（弹出卡片，和颜色按钮同风格）
        ep.addWidget(QLabel("图标"))
        icon_row = QHBoxLayout()
        self._icon_btn = QPushButton("📁")
        self._icon_btn.setFixedSize(40, 32)
        self._icon_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._icon_btn.setStyleSheet(
            "QPushButton { background: #1e1e34; border: 1px solid #3a3a50; "
            "border-radius: 6px; font-size: 18px; }"
            "QPushButton:hover { border-color: #7c5cfc; }"
        )
        self._icon_btn.clicked.connect(self._open_icon_picker)
        icon_row.addWidget(self._icon_btn)
        icon_row.addStretch()
        ep.addLayout(icon_row)

        # 该分类的应用
        ep.addWidget(QLabel("已分配的应用"))
        self._cat_app_list = QListWidget()
        self._cat_app_list.setMaximumHeight(120)
        self._cat_app_list.setFrameShape(QFrame.Shape.NoFrame)
        self._cat_app_list.setStyleSheet("background: transparent;")
        ep.addWidget(self._cat_app_list)

        # 添加应用到分类
        add_app_row = QHBoxLayout()
        self._add_app_btn = QPushButton("+ 添加应用")
        self._add_app_btn.setStyleSheet(
            "background: #4a4a6a; border: none; border-radius: 4px; padding: 6px 12px; color: #fff; font-size: 12px;"
        )
        self._add_app_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_app_btn.clicked.connect(self._pick_app_for_category)
        add_app_row.addWidget(self._add_app_btn)
        add_app_row.addStretch()
        ep.addLayout(add_app_row)

        # 保存 / 删除
        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("保存")
        self._save_btn.setStyleSheet(
            "QPushButton { background: #7c5cfc; border: none; border-radius: 4px; "
            "padding: 8px 24px; color: #fff; font-weight: 600; }"
            "QPushButton:hover { background: #6a4acc; }"
        )
        self._save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_btn.clicked.connect(self._save_category)
        self._delete_btn = QPushButton("删除")
        self._delete_btn.setStyleSheet(
            "QPushButton { background: #f44336; border: none; border-radius: 4px; "
            "padding: 8px 24px; color: #fff; font-weight: 600; }"
            "QPushButton:hover { background: #d32f2f; }"
        )
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.clicked.connect(self._delete_category)
        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._delete_btn)
        btn_row.addStretch()
        ep.addLayout(btn_row)

        right.addWidget(self._edit_panel, stretch=1)
        right.addStretch()

        split.addLayout(right, stretch=3)
        layout.addLayout(split, stretch=1)

        self._refresh_selector()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _select_category(self, cat_id: int):
        """从选择器点击分类 → 加载编辑面板."""
        if not self._repo:
            return
        try:
            cats = self._repo.get_all_categories()
            for cat in cats:
                if cat.id == cat_id:
                    self._edit_category(cat)
                    return
        except Exception:
            pass

    def set_repo(self, repo: Repository) -> None:
        self._repo = repo
        self._refresh_selector()

    def refresh(self):
        """页面切换时调用的公开刷新入口."""
        self._refresh_selector()
        if self._editing_cat_id is not None:
            self._refresh_app_list()

    # ── 紧凑分类选择器（彩色图标按钮） ─────────────────────

    def _refresh_selector(self):
        """重建分类选择器（跟随主题，无分类颜色干扰）. """
        self._clear_layout(self._cat_selector_layout)
        for btn in self._cat_selector.buttons():
            self._cat_selector.removeButton(btn)

        if not self._repo:
            return

        try:
            is_dark = ThemeManager.instance().current_name == "dark"
            bg = "#25253a" if is_dark else "#ffffff"
            bg_hover = "#2a2a44" if is_dark else "#f0ecff"
            bg_checked = "#7c5cfc"
            txt = "#e0e0e8" if is_dark else "#1a1a2e"
            txt_checked = "#ffffff"
            border = "#3a3a50" if is_dark else "#e0e0e8"

            app_cats = self._repo.get_all_app_categories()
            count_by_cat: dict[int, int] = {}
            for ac in app_cats:
                count_by_cat[ac["category_id"]] = count_by_cat.get(ac["category_id"], 0) + 1

            cats = self._repo.get_all_categories()
            for cat in cats:
                icon = cat.icon or "📁"
                count = count_by_cat.get(cat.id, 0)
                count_str = f"({count})" if count else ""
                btn = QPushButton(f"  {icon}  {cat.name}  {count_str}")
                btn.setCheckable(True)
                btn.setFixedHeight(40)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(
                    f"QPushButton {{ background: {bg}; border: 1px solid {border}; "
                    f"border-radius: 8px; text-align: left; padding: 4px 10px; color: {txt}; "
                    f"font-size: 12px; font-weight: 600; }}"
                    f"QPushButton:hover {{ background: {bg_hover}; }}"
                    f"QPushButton:checked {{ background: {bg_checked}; border-color: {bg_checked}; "
                    f"color: {txt_checked}; }}"
                )
                self._cat_selector.addButton(btn, cat.id)
                self._cat_selector_layout.addWidget(btn)
        except Exception:
            pass

    # ── 编辑面板 ─────────────────────────────────────────

    def _start_new_category(self):
        """清空编辑面板，准备新建分类."""
        self._editing_cat_id = None
        self._edit_name.clear()
        self._selected_color_edit = "#7c5cfc"
        self._edit_color_btn.setStyleSheet(f"background: {self._selected_color_edit}; border-radius: 4px; border: none;")
        self._selected_icon = "📁"
        self._icon_btn.setText("📁")
        self._cat_app_list.clear()
        self._edit_panel.setVisible(True)

    def _edit_category(self, cat):
        """加载分类数据到编辑面板."""
        self._editing_cat_id = cat.id
        self._edit_name.setText(cat.name)
        self._selected_color_edit = cat.color or "#7c5cfc"
        self._edit_color_btn.setStyleSheet(f"background: {self._selected_color_edit}; border-radius: 4px; border: none;")
        self._selected_icon = cat.icon or "📁"
        self._icon_btn.setText(self._selected_icon)

        # 加载应用列表
        self._refresh_app_list()
        self._edit_panel.setVisible(True)

    def _refresh_app_list(self):
        self._cat_app_list.clear()
        if not self._repo or self._editing_cat_id is None:
            return
        try:
            all_app_cats = self._repo.get_all_app_categories()
            today = date.today()
            for ac in all_app_cats:
                if ac["category_id"] == self._editing_cat_id:
                    raw = ac["process_name"]
                    disp = strip_ext(raw)
                    icon = get_app_icon(raw)

                    # 获取今日使用时长
                    total = self._repo.get_total_duration_by_date(today)
                    usage = self._repo.get_usage_summary_by_date(today, "process_name")
                    secs = 0
                    for u in usage:
                        if u["name"] == raw:
                            secs = u["total_seconds"]
                            break

                    h, m = secs // 3600, (secs % 3600) // 60
                    if h:
                        time_str = f"{h}h {m:02d}m"
                    elif m:
                        time_str = f"{m:02d}m"
                    else:
                        time_str = f"{secs}s"

                    # 行容器
                    widget = QFrame()
                    widget.setStyleSheet(
                        "QFrame { background: #1e1e34; border-radius: 6px; border: 1px solid #3a3a50; }"
                        "QFrame:hover { border-color: #5a5a7a; }"
                    )
                    lo = QHBoxLayout(widget)
                    lo.setContentsMargins(6, 4, 6, 4)
                    lo.setSpacing(6)

                    # 图标
                    icon_lbl = QLabel()
                    p = icon.pixmap(18, 18)
                    from PyQt6.QtGui import QPixmap as _QP
                    icon_lbl.setPixmap(p if p and not p.isNull() else _QP())
                    icon_lbl.setFixedSize(20, 20)

                    # 名称
                    name_lbl = QLabel(disp)
                    name_lbl.setStyleSheet("color: #e0e0e8; font-size: 12px; background: transparent; border: none;")

                    # 时长
                    time_lbl = QLabel(time_str)
                    time_lbl.setStyleSheet("color: #606080; font-size: 11px; background: transparent; border: none;")

                    # 删除
                    del_btn = QPushButton("✕")
                    del_btn.setFixedSize(20, 20)
                    del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    del_btn.setStyleSheet(
                        "QPushButton { background: transparent; border: none; border-radius: 10px; "
                        "color: #606080; font-size: 11px; }"
                        "QPushButton:hover { background: #f44336; color: #fff; }"
                    )
                    del_btn.clicked.connect(lambda checked, p=raw: self._remove_app_from_cat(p))

                    lo.addWidget(icon_lbl)
                    lo.addWidget(name_lbl, stretch=1)
                    lo.addWidget(time_lbl)
                    lo.addWidget(del_btn)

                    item = QListWidgetItem()
                    item.setSizeHint(QSize(200, 36))
                    self._cat_app_list.addItem(item)
                    self._cat_app_list.setItemWidget(item, widget)
        except Exception as e:
            print(f"刷新应用列表失败: {e}")

    def _remove_app_from_cat(self, process_name: str):
        """从分类中移除应用映射."""
        if self._repo:
            self._repo.delete_app_category(process_name)
            self._refresh_app_list()
            self._refresh_selector()

    def _pick_edit_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self._edit_color_btn.setStyleSheet(f"background: {color.name()}; border-radius: 4px; border: none;")
            self._selected_color_edit = color.name()

    def _open_icon_picker(self):
        """弹出图标选择卡片对话框."""
        from PyQt6.QtWidgets import QDialog
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        dlg.setStyleSheet(
            "QDialog { background: #25253a; border: 1px solid #4a4a6a; border-radius: 12px; }"
        )
        dlg.setFixedSize(280, 220)
        lo = QVBoxLayout(dlg)
        lo.setContentsMargins(12, 12, 12, 12)
        lo.addWidget(QLabel("选择图标", styleSheet="color: #fff; font-size: 13px; font-weight: 700;"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setSpacing(4)

        group = QButtonGroup(dlg)
        group.setExclusive(True)

        def on_pick(idx: int):
            if 0 <= idx < len(_PRESET_ICONS):
                self._selected_icon = _PRESET_ICONS[idx]
                self._icon_btn.setText(self._selected_icon)
            dlg.accept()

        for idx, ico in enumerate(_PRESET_ICONS):
            btn = QPushButton(ico)
            btn.setCheckable(True)
            btn.setFixedSize(36, 36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background: #1e1e34; border: 1px solid #3a3a50; "
                "border-radius: 6px; font-size: 18px; }"
                "QPushButton:hover { border-color: #7c5cfc; }"
                "QPushButton:checked { background: #7c5cfc; border-color: #7c5cfc; }"
            )
            btn.clicked.connect(lambda checked, i=idx: on_pick(i))
            group.addButton(btn, idx)
            grid.addWidget(btn, idx // 6, idx % 6)

        scroll.setWidget(inner)
        lo.addWidget(scroll)
        dlg.exec()

    # ── 保存 / 删除 ──────────────────────────────────────

    def _save_category(self):
        name = self._edit_name.text().strip()
        if not name or not self._repo:
            return
        try:
            color_hex = getattr(self, "_selected_color_edit", "#7c5cfc")
            if self._editing_cat_id is not None:
                # 更新已有分类
                from pulse.db.models import Category
                with self._repo.session() as s:
                    cat = s.query(Category).filter(Category.id == self._editing_cat_id).first()
                    if cat:
                        cat.name = name
                        cat.color = color_hex
                        cat.icon = self._selected_icon
                is_dark = ThemeManager.instance().current_name == "dark"
                bg = "#25253a" if is_dark else "#ffffff"
                bg_hover = "#2a2a44" if is_dark else "#f0ecff"
                txt = "#e0e0e8" if is_dark else "#1a1a2e"
                border = "#3a3a50" if is_dark else "#e0e0e8"
                for btn in self._cat_selector.buttons():
                    if self._cat_selector.id(btn) == self._editing_cat_id:
                        btn.setText(f"  {self._selected_icon}  {name}")
                        btn.setStyleSheet(
                            f"QPushButton {{ background: {bg}; border: 1px solid {border}; "
                            f"border-radius: 8px; text-align: left; padding: 4px 10px; color: {txt}; "
                            f"font-size: 12px; font-weight: 600; }}"
                            f"QPushButton:hover {{ background: {bg_hover}; }}"
                            f"QPushButton:checked {{ background: #7c5cfc; border-color: #7c5cfc; "
                            f"color: #ffffff; }}"
                        )
                        break
            else:
                # 新建
                cat = self._repo.create_category(name, color=color_hex, icon=self._selected_icon)
                is_dark = ThemeManager.instance().current_name == "dark"
                bg = "#25253a" if is_dark else "#ffffff"
                bg_hover = "#2a2a44" if is_dark else "#f0ecff"
                txt = "#e0e0e8" if is_dark else "#1a1a2e"
                border = "#3a3a50" if is_dark else "#e0e0e8"
                btn = QPushButton(f"  {self._selected_icon}  {name}")
                btn.setCheckable(True)
                btn.setFixedHeight(40)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(
                    f"QPushButton {{ background: {bg}; border: 1px solid {border}; "
                    f"border-radius: 8px; text-align: left; padding: 4px 10px; color: {txt}; "
                    f"font-size: 12px; font-weight: 600; }}"
                    f"QPushButton:hover {{ background: {bg_hover}; }}"
                    f"QPushButton:checked {{ background: #7c5cfc; border-color: #7c5cfc; "
                    f"color: #ffffff; }}"
                )
                self._cat_selector.addButton(btn, cat.id)
                self._cat_selector_layout.addWidget(btn)
            self._edit_panel.setVisible(False)
        except Exception as e:
            print(f"保存分类失败: {e}")

    def _delete_category(self):
        if self._editing_cat_id is None or not self._repo:
            return
        try:
            self._repo.delete_category(self._editing_cat_id)
            self._edit_panel.setVisible(False)
            # 移除对应按钮
            for btn in self._cat_selector.buttons():
                if self._cat_selector.id(btn) == self._editing_cat_id:
                    self._cat_selector.removeButton(btn)
                    btn.deleteLater()
                    break
        except Exception as e:
            print(f"删除分类失败: {e}")

    # ── AI 自动分类 ─────────────────────────────────────

    def _do_ai_classify(self):
        if not self._repo or not self._config_mgr:
            return
        cfg = self._config_mgr.config.llm
        if not cfg.api_key:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "提示", "请先在设置中配置 API Key")
            return
        self._ai_btn.setEnabled(False)
        self._ai_btn.setText("🤖 分类中...")
        svc = ClassifierService(self._repo, cfg)
        result = svc.auto_classify()
        self._refresh_selector()
        self._ai_btn.setEnabled(True)
        if result["errors"]:
            self._ai_btn.setText(f"🤖 出错: {result['errors'][0]}")
        elif result["success"]:
            self._ai_btn.setText(f"🤖 已分类 {result['success']} 个 ✓")
            QTimer.singleShot(3000, lambda: self._ai_btn.setText("🤖 分类"))
        else:
            if result["hot"] == 0:
                self._ai_btn.setText("🤖 暂无热门未分类应用")
            else:
                self._ai_btn.setText("🤖 没有需要分类的应用")

    # ── 应用分配（文件选择器） ────────────────────────────

    def _pick_app_for_category(self):
        if not self._repo:
            return
        # 如果是新建还没保存的分类，先自动保存
        if self._editing_cat_id is None:
            name = self._edit_name.text().strip()
            if not name:
                return
            try:
                color_hex = getattr(self, "_selected_color_edit", "#7c5cfc")
                cat = self._repo.create_category(name, color=color_hex, icon=self._selected_icon)
                self._editing_cat_id = cat.id
                self._refresh_selector()
            except Exception as e:
                print(f"自动保存分类失败: {e}")
                return

        path, _ = QFileDialog.getOpenFileName(
            self, "选择应用", "C:\\Program Files",
            "可执行文件 (*.exe);;所有文件 (*)"
        )
        if not path:
            return
        # 从完整路径中提取纯文件名，兼容 \ 和 / 两种分隔符
        process_name = os.path.basename(path)
        try:
            self._repo.save_app_category(process_name, self._editing_cat_id)
            self._refresh_app_list()
            self._refresh_selector()
        except Exception as e:
            print(f"添加应用失败: {e}")
