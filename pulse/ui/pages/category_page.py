"""分类管理页面 —— 网格卡片 / 图标选择 / 应用分配."""

from typing import Optional

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QButtonGroup, QColorDialog, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from PyQt6.QtCore import QTimer

from pulse.core.classifier import ClassifierService
from pulse.db.repository import Repository
from pulse.utils.config import ConfigManager

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

        # ── 左栏：分类卡片网格 ──
        left = QVBoxLayout()
        left_label = QLabel("所有分类")
        left_label.setStyleSheet("font-size: 14px; font-weight: 600;")
        left.addWidget(left_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        self._cat_grid_container = QWidget()
        self._cat_grid = QGridLayout(self._cat_grid_container)
        self._cat_grid.setSpacing(8)
        scroll.setWidget(self._cat_grid_container)
        left.addWidget(scroll, stretch=1)

        add_btn = QPushButton("+ 新分类")
        add_btn.setStyleSheet(
            "QPushButton { background: #7c5cfc; border: none; border-radius: 8px; "
            "padding: 10px; color: #fff; font-size: 14px; font-weight: 600; }"
            "QPushButton:hover { background: #6a4acc; }"
        )
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.clicked.connect(self._start_new_category)
        left.addWidget(add_btn)

        # AI 自动分类
        self._ai_btn = QPushButton("🤖 AI 自动分类")
        self._ai_btn.setStyleSheet(
            "QPushButton { background: #4a4a6a; border: none; border-radius: 8px; "
            "padding: 10px; color: #fff; font-size: 13px; font-weight: 600; margin-top: 4px; }"
            "QPushButton:hover { background: #5a5a7a; }"
            "QPushButton:disabled { color: #606080; }"
        )
        self._ai_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_btn.clicked.connect(self._do_ai_classify)
        left.addWidget(self._ai_btn)

        split.addLayout(left, stretch=2)

        # ── 右栏：编辑面板 ──
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

        # 图标选择
        ep.addWidget(QLabel("图标"))
        icon_grid = QGridLayout()
        icon_grid.setSpacing(4)
        self._icon_group = QButtonGroup(self)
        self._icon_group.setExclusive(True)
        self._icon_group.idClicked.connect(self._on_icon_selected)
        self._selected_icon = "📁"
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
            self._icon_group.addButton(btn, idx)
            icon_grid.addWidget(btn, idx // 6, idx % 6)
        ep.addLayout(icon_grid)

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

        self._refresh_grid()

    def set_repo(self, repo: Repository) -> None:
        self._repo = repo
        self._refresh_grid()

    # ── 分类卡片网格 ─────────────────────────────────────

    def _refresh_grid(self):
        """重新绘制分类卡片网格."""
        # 清空
        while self._cat_grid.count():
            item = self._cat_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._repo:
            return

        try:
            cats = self._repo.get_all_categories()
            app_cats = self._repo.get_all_app_categories()
            app_count = {}
            for ac in app_cats:
                cid = ac["category_id"]
                app_count[cid] = app_count.get(cid, 0) + 1

            for i, cat in enumerate(cats):
                card = self._make_category_card(cat, app_count.get(cat.id, 0))
                self._cat_grid.addWidget(card, i // 3, i % 3)
        except Exception:
            pass

    def _make_category_card(self, cat, app_count: int) -> QPushButton:
        """创建一个分类卡片按钮."""
        color = cat.color or "#607D8B"
        icon = cat.icon or "📁"
        btn = QPushButton()
        btn.setFixedSize(160, 100)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background: {color}22; border: 2px solid {color}; "
            f"border-radius: 10px; text-align: center; padding: 8px; }}"
            f"QPushButton:hover {{ background: {color}44; }}"
        )

        lo = QVBoxLayout(btn)
        lo.setSpacing(4)
        lo.setContentsMargins(8, 8, 8, 8)

        icon_label = QLabel(icon)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 28px; background: transparent;")
        lo.addWidget(icon_label, stretch=1)

        name_label = QLabel(cat.name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 600; background: transparent;")
        lo.addWidget(name_label)

        count_label = QLabel(f"{app_count} 个应用")
        count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count_label.setStyleSheet("color: #808098; font-size: 11px; background: transparent;")
        lo.addWidget(count_label)

        btn.clicked.connect(lambda checked, c=cat: self._edit_category(c))
        return btn

    # ── 编辑面板 ─────────────────────────────────────────

    def _start_new_category(self):
        """清空编辑面板，准备新建分类."""
        self._editing_cat_id = None
        self._edit_name.clear()
        self._edit_color_btn.setStyleSheet("background: #7c5cfc; border-radius: 4px; border: none;")
        self._selected_icon = "📁"
        # 取消所有图标选中
        for btn in self._icon_group.buttons():
            btn.setChecked(False)
        self._cat_app_list.clear()
        self._edit_panel.setVisible(True)

    def _edit_category(self, cat):
        """加载分类数据到编辑面板."""
        self._editing_cat_id = cat.id
        self._edit_name.setText(cat.name)
        self._edit_color_btn.setStyleSheet(f"background: {cat.color}; border-radius: 4px; border: none;")
        self._selected_icon = cat.icon or "📁"

        # 选中对应图标
        for btn in self._icon_group.buttons():
            idx = self._icon_group.id(btn)
            if idx < len(_PRESET_ICONS) and _PRESET_ICONS[idx] == self._selected_icon:
                btn.setChecked(True)
                break

        # 加载应用列表
        self._refresh_app_list()
        self._edit_panel.setVisible(True)

    def _refresh_app_list(self):
        self._cat_app_list.clear()
        if not self._repo or self._editing_cat_id is None:
            return
        try:
            all_app_cats = self._repo.get_all_app_categories()
            for ac in all_app_cats:
                if ac["category_id"] == self._editing_cat_id:
                    item = QListWidgetItem(f"  {ac['process_name']}")
                    item.setData(Qt.ItemDataRole.UserRole, ac["process_name"])
                    self._cat_app_list.addItem(item)
        except Exception:
            pass

    def _pick_edit_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self._edit_color_btn.setStyleSheet(f"background: {color.name()}; border-radius: 4px; border: none;")
            self._selected_color_edit = color.name()

    def _on_icon_selected(self, idx: int):
        if 0 <= idx < len(_PRESET_ICONS):
            self._selected_icon = _PRESET_ICONS[idx]

    # ── 保存 / 删除 ──────────────────────────────────────

    def _save_category(self):
        name = self._edit_name.text().strip()
        if not name or not self._repo:
            return
        try:
            color_hex = getattr(self, "_selected_color_edit", "#7c5cfc")
            if self._editing_cat_id is not None:
                # 更新已有分类（删除重建）
                from pulse.db.models import Category
                with self._repo.session() as s:
                    cat = s.query(Category).filter(Category.id == self._editing_cat_id).first()
                    if cat:
                        cat.name = name
                        cat.color = color_hex
                        cat.icon = self._selected_icon
            else:
                # 新建
                self._repo.create_category(name, color=color_hex, icon=self._selected_icon)
            self._edit_panel.setVisible(False)
            self._refresh_grid()
        except Exception as e:
            print(f"保存分类失败: {e}")

    def _delete_category(self):
        if self._editing_cat_id is None or not self._repo:
            return
        try:
            self._repo.delete_category(self._editing_cat_id)
            self._edit_panel.setVisible(False)
            self._refresh_grid()
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
        result = svc.reclassify()
        self._refresh_grid()
        self._ai_btn.setEnabled(True)
        if result["errors"]:
            self._ai_btn.setText(f"🤖 分类出错: {result['errors'][0]}")
        elif result["success"]:
            self._ai_btn.setText(f"🤖 已分类 {result['success']} 个应用 ✓")
            QTimer.singleShot(3000, lambda: self._ai_btn.setText("🤖 AI 自动分类"))
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
                self._refresh_grid()
            except Exception as e:
                print(f"自动保存分类失败: {e}")
                return

        path, _ = QFileDialog.getOpenFileName(
            self, "选择应用", "C:\\Program Files",
            "可执行文件 (*.exe);;所有文件 (*)"
        )
        if not path:
            return
        process_name = path.rsplit("\\", 1)[-1]
        try:
            self._repo.save_app_category(process_name, self._editing_cat_id)
            self._refresh_app_list()
            self._refresh_grid()
        except Exception as e:
            print(f"添加应用失败: {e}")
