"""任务详情模态对话框 —— Notion 风格，屏幕中央弹出."""

from datetime import date, datetime
from typing import Optional

from PyQt6.QtCore import QPoint, Qt, pyqtSignal  # type: ignore
from PyQt6.QtWidgets import (  # type: ignore
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QTextEdit,
    QTimeEdit, QVBoxLayout, QWidget,
)

from pulse.db.repository import Repository
from pulse.ui.widgets.styled_combo import StyledCombo


class _DatePickerButton(QPushButton):
    """日期选择按钮 —— 点击弹出独立日历对话框（比 QDateEdit 弹窗渲染可靠）. """

    dateChanged = pyqtSignal()  # 日期变化信号（与 QDateEdit 兼容）

    def __init__(self, initial_date: date, parent=None):
        super().__init__(parent)
        self._date = initial_date
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QPushButton { padding: 4px 10px; border-radius: 6px; background: #25253a; "
            "color: #e0e0e8; border: 1px solid #3a3a50; font-size: 12px; }"
            "QPushButton:hover { border-color: #7c5cfc; }"
        )
        self.clicked.connect(self._open_calendar)
        self._update_text()

    def date(self) -> date:
        return self._date

    def setDate(self, d: date):
        self._date = d
        self._update_text()
        self.dateChanged.emit()

    def _update_text(self):
        self.setText(self._date.strftime("%Y-%m-%d"))

    def _open_calendar(self):
        from pulse.ui.widgets.date_picker_dialog import DatePickerDialog
        dlg = DatePickerDialog(self._date, self.window())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            picked = dlg.get_selected()
            if picked:
                self.setDate(picked)


class _FieldEdit(QTextEdit):
    """字段文本框 —— 滚轮事件交给父级滚动区域，避免内部滚动方向错乱."""

    def wheelEvent(self, event):
        event.ignore()  # 让事件冒泡到对话框的滚动区域


class _MenuOption(QFrame):
    """评论 ⋮ 菜单的小卡片选项 —— 可自定义颜色，hover 高亮."""

    clicked = pyqtSignal()

    def __init__(self, text: str, color: str = "#e0e0e8", parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        lo = QHBoxLayout(self)
        lo.setContentsMargins(14, 0, 14, 0)
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {color}; font-size: 13px; background: transparent;")
        lo.addWidget(lbl)
        self._apply(False)

    def _apply(self, hover: bool):
        self.setStyleSheet(
            "QFrame { background: %s; border-radius: 6px; }"
            % ("#3a3a5a" if hover else "transparent")
        )

    def enterEvent(self, event):
        self._apply(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply(False)
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class _CommentActionsCard(QFrame):
    """评论 ⋮ 展开的小卡片 —— 含编辑 / 删除，点击外部自动关闭."""

    def __init__(self, on_edit, on_delete, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(
            "QFrame { background: #25253a; border: 1px solid #3a3a50; border-radius: 8px; }"
        )
        lo = QVBoxLayout(self)
        lo.setContentsMargins(6, 6, 6, 6)
        lo.setSpacing(2)

        edit_opt = _MenuOption("✏️ 编辑")
        edit_opt.clicked.connect(lambda: (on_edit(), self.close()))
        del_opt = _MenuOption("🗑 删除", color="#f44336")
        del_opt.clicked.connect(lambda: (on_delete(), self.close()))

        lo.addWidget(edit_opt)
        lo.addWidget(del_opt)
        self.setFixedWidth(132)


class TaskDetailDialog(QDialog):
    """屏幕中央出现的 Notion 风格任务详情卡片."""

    def __init__(self, task_id: int, repo: Repository, parent=None):
        super().__init__(parent)
        self._task_id = task_id
        self._repo = repo
        self._task = repo.get_task_by_id(task_id)
        self._field_edits: list = []  # 所有字段 edit 引用，用于统一重测尺寸
        self._editing_comment_id: Optional[int] = None  # 正在编辑的评论 id
        self._comment_edit: Optional[QLineEdit] = None  # 评论编辑输入框引用

        # 模态 + 无边框
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setModal(True)
        self.setFixedSize(580, 620)

        # 整体背景
        self.setStyleSheet("QDialog { background: #1e1e34; border-radius: 14px; border: 1px solid #3a3a50; }")

        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)

        # ── 内边容器 ──
        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_lo = QVBoxLayout(inner)
        inner_lo.setContentsMargins(20, 10, 20, 14)
        inner_lo.setSpacing(6)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        scroll.setWidget(inner)
        lo.addWidget(scroll)

        # ── 关闭按钮 ──
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background: #3a3a5a; border: none; border-radius: 14px; "
            "color: #a0a0b8; font-size: 14px; }"
            "QPushButton:hover { background: #f44336; color: #fff; }"
        )
        close_btn.clicked.connect(self.close)
        close_row.addWidget(close_btn)
        inner_lo.addLayout(close_row)

        if not self._task:
            inner_lo.addWidget(QLabel("任务不存在"))
            return

        # ── 标题（不可见边框） ──
        self._title_edit = QLineEdit(self._task.title)
        self._title_edit.setStyleSheet(
            "QLineEdit { font-size: 20px; font-weight: 700; padding: 8px 0; border: none; "
            "background: transparent; color: #ffffff; }"
            "QLineEdit:focus { border-bottom: 2px solid #7c5cfc; }"
        )
        self._title_edit.editingFinished.connect(self._save_title)
        inner_lo.addWidget(self._title_edit)

        # ── 日期范围（简洁） ──
        date_row = QHBoxLayout()
        date_row.setSpacing(8)
        start_lbl = QLabel("开始")
        start_lbl.setStyleSheet("color: #808098; font-size: 12px; background: transparent;")
        self._start_date = self._make_date_edit(self._task.date)
        end_lbl = QLabel("结束")
        end_lbl.setStyleSheet("color: #808098; font-size: 12px; background: transparent;")
        self._end_date = self._make_date_edit(self._task.end_date or self._task.date)
        self._end_date.dateChanged.connect(self._save_dates)
        date_row.addWidget(start_lbl)
        date_row.addWidget(self._start_date)
        date_row.addSpacing(12)
        date_row.addWidget(end_lbl)
        date_row.addWidget(self._end_date)
        date_row.addStretch()
        inner_lo.addLayout(date_row)

        # ── 提醒（普通 / 定时） ──
        remind_row = QHBoxLayout()
        remind_row.setSpacing(8)
        self._remind_type = StyledCombo()
        self._remind_type.addItems(["普通任务", "定时提醒"])
        self._remind_type.setFixedWidth(100)
        self._remind_type.setStyleSheet(
            "QComboBox { padding: 4px 8px; border-radius: 6px; background: #25253a; "
            "color: #e0e0e8; border: 1px solid #3a3a50; font-size: 12px; }"
        )
        self._remind_type.currentIndexChanged.connect(self._on_remind_type_changed)

        self._remind_date = self._make_date_edit(self._task.date)
        self._remind_time = QTimeEdit()
        self._remind_time.setDisplayFormat("HH:mm")
        self._remind_time.setStyleSheet(
            "QTimeEdit { padding: 4px 8px; border-radius: 6px; background: #25253a; "
            "color: #e0e0e8; border: 1px solid #3a3a50; font-size: 12px; }"
        )
        if self._task.remind_at:
            self._remind_type.setCurrentIndex(1)
            self._remind_date.setDate(self._task.remind_at.date())
            self._remind_time.setTime(self._task.remind_at.time())
        else:
            self._remind_type.setCurrentIndex(0)

        # 联动保存：日期/时间变化时更新提醒
        self._remind_date.dateChanged.connect(self._save_reminder)
        self._remind_time.timeChanged.connect(self._save_reminder)

        remind_row.addWidget(self._remind_type)
        remind_row.addWidget(self._remind_date)
        remind_row.addWidget(self._remind_time)
        remind_row.addStretch()
        inner_lo.addLayout(remind_row)
        self._on_remind_type_changed(self._remind_type.currentIndex())

        # 删除
        del_btn = QPushButton("删除此任务")
        del_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px solid #4a3030; border-radius: 6px; "
            "padding: 6px 14px; color: #f44336; font-size: 11px; }"
            "QPushButton:hover { background: #3a2020; }"
        )
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.clicked.connect(self._delete_task)
        inner_lo.addWidget(del_btn)

        # ── 字段（带边框） ──
        inner_lo.addWidget(self._mk_label("字段"))
        self._fields_layout = QVBoxLayout()
        self._fields_layout.setSpacing(4)
        self._rebuild_fields()
        inner_lo.addLayout(self._fields_layout)

        add_field_btn = QPushButton("+ 添加字段")
        add_field_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px dashed #3a3a50; border-radius: 6px; "
            "padding: 8px; color: #606080; font-size: 12px; }"
            "QPushButton:hover { border-color: #7c5cfc; color: #7c5cfc; }"
        )
        add_field_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_field_btn.clicked.connect(self._add_field)
        inner_lo.addWidget(add_field_btn)

        # ── 清单（功能清单模块） ──
        inner_lo.addWidget(self._mk_label("清单"))
        self._checklists_layout = QVBoxLayout()
        self._checklists_layout.setSpacing(8)
        self._rebuild_checklists()
        inner_lo.addLayout(self._checklists_layout)

        add_cl_btn = QPushButton("+ 添加清单")
        add_cl_btn.setStyleSheet(
            "QPushButton { background: transparent; border: 1px dashed #3a3a50; border-radius: 6px; "
            "padding: 8px; color: #606080; font-size: 12px; }"
            "QPushButton:hover { border-color: #7c5cfc; color: #7c5cfc; }"
        )
        add_cl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_cl_btn.clicked.connect(self._add_checklist)
        inner_lo.addWidget(add_cl_btn)

        # ── 评论 ──
        inner_lo.addWidget(self._mk_label("评论"))
        self._comments_layout = QVBoxLayout()
        self._comments_layout.setSpacing(4)
        self._rebuild_comments()
        inner_lo.addLayout(self._comments_layout)

        comment_row = QHBoxLayout()
        self._comment_input = QLineEdit()
        self._comment_input.setPlaceholderText("写评论...")
        self._comment_input.setStyleSheet(
            "QLineEdit { padding: 8px; border-radius: 6px; background: #25253a; "
            "color: #e0e0e8; border: 1px solid #3a3a50; font-size: 13px; }"
            "QLineEdit:focus { border-color: #7c5cfc; }"
        )
        self._comment_input.returnPressed.connect(self._post_comment)
        cs = QPushButton("发送")
        cs.setStyleSheet(
            "QPushButton { background: #7c5cfc; border: none; border-radius: 6px; "
            "padding: 8px 18px; color: #fff; font-weight: 600; font-size: 12px; }"
            "QPushButton:hover { background: #6a4acc; }"
        )
        cs.setCursor(Qt.CursorShape.PointingHandCursor)
        cs.clicked.connect(self._post_comment)
        comment_row.addWidget(self._comment_input)
        comment_row.addWidget(cs)
        inner_lo.addLayout(comment_row)

        # 剩余空间全部挤到底部，中间不留空隙
        inner_lo.addStretch(1)

    @staticmethod
    def _make_date_edit(value) -> _DatePickerButton:
        """创建日期选择按钮（点击弹出独立日历对话框）. """
        return _DatePickerButton(value)

    @staticmethod
    def _mk_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 12px; color: #808098; margin-top: 4px; background: transparent;")
        return lbl

    # ── 字段 ──────────────────────────────────────────

    def _rebuild_fields(self):
        """重新查询任务获取最新字段（避免 ORM 缓存导致删除/新增不生效）. """
        self._clear_layout(self._fields_layout)
        self._field_edits = []
        if not self._repo:
            return
        self._task = self._repo.get_task_by_id(self._task_id)
        if not self._task:
            return
        for field in self._task.fields:
            self._add_field_widget(field.id, field.content)

    @staticmethod
    def _resize_to_content(edit: QTextEdit):
        """按内容实际高度自适应（Notion 风格）：不裁剪、不用内部滚轮，
        整个对话框滚动。空字段统一 30px."""
        doc_h = int(edit.document().size().height()) + 8
        h = max(30, doc_h)
        edit.setFixedHeight(h)
        # 外层 frame 同步高度
        parent = edit.parentWidget()
        if parent:
            parent.setFixedHeight(h + 10)

    def _add_field_widget(self, fid: int, content: str):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: #25253a; border: 1px solid #3a3a50; border-radius: 8px; "
            "padding: 2px; }"
            "QFrame:hover { border-color: #5a5a7a; }"
        )
        lo = QHBoxLayout(frame)
        lo.setContentsMargins(6, 4, 6, 4)
        lo.setSpacing(4)

        edit = _FieldEdit()
        edit.setPlainText(content)
        edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        edit.setStyleSheet(
            "QTextEdit { background: transparent; border: none; color: #e0e0e8; "
            "font-size: 13px; padding: 2px; }"
        )

        def on_text_changed():
            self._repo.update_task_field(fid, edit.toPlainText())
            self._resize_to_content(edit)  # 每次输入都按内容调整

        edit.textChanged.connect(on_text_changed)
        # 初始按内容调整（空字段统一 30px，有内容的展开显示全部）
        self._resize_to_content(edit)
        self._field_edits.append(edit)

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 12px; "
            "color: #606080; font-size: 12px; }"
            "QPushButton:hover { background: #f44336; color: #fff; }"
        )
        del_btn.clicked.connect(lambda checked, fid=fid: self._delete_field(fid))

        lo.addWidget(edit, stretch=1)
        lo.addWidget(del_btn)
        self._fields_layout.addWidget(frame)

    def _delete_field(self, fid: int):
        """删除字段并立即刷新（独立方法便于排查）. """
        try:
            self._repo.delete_task_field(fid)
        except Exception as e:
            print(f"删除字段失败: {e}")
        self._rebuild_fields()

    def _resize_all_fields(self):
        """布局变化后重新测量所有字段高度（防止换行后尺寸失准）. """
        for edit in self._field_edits:
            self._resize_to_content(edit)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 对话框尺寸变化 → 字段宽度变化 → 换行变化 → 重新测高
        from PyQt6.QtCore import QTimer as _QT
        _QT.singleShot(0, self._resize_all_fields)

    # ── 清单（功能清单模块） ──────────────────────────────

    def _rebuild_checklists(self):
        """重建清单区（新增/勾选/删除后整体刷新）. """
        self._clear_layout(self._checklists_layout)
        if not self._task or not self._repo:
            return
        for cl in self._repo.get_checklists(self._task_id):
            self._add_checklist_widget(cl)

    def _add_checklist_widget(self, cl):
        items = list(cl.items or [])
        done = sum(1 for it in items if it.done)
        total = len(items)
        complete = total > 0 and done == total

        frame = QFrame()
        frame.setObjectName("checklistCard")
        frame.setStyleSheet(
            "QFrame#checklistCard { background: #25253a; border-radius: 8px; padding: 2px; "
            "border: 1px solid %s; }"
            % ("#4caf50" if complete else "#3a3a50")
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(10, 8, 8, 8)
        v.setSpacing(6)

        # ── 头部：标题 + 进度徽标 + 删除 ──
        head = QHBoxLayout()
        head.setSpacing(8)

        title_edit = QLineEdit(cl.title)
        tf = title_edit.font()
        tf.setStrikeOut(complete)
        title_edit.setFont(tf)
        title_edit.setStyleSheet(
            "QLineEdit { background: transparent; border: none; color: #ffffff; "
            "font-size: 14px; font-weight: 600; padding: 2px; }"
        )
        title_edit.editingFinished.connect(
            lambda e=title_edit, cid=cl.id: self._save_checklist_title(cid, e.text())
        )
        head.addWidget(title_edit, stretch=1)

        badge = QLabel("✓ 已完成" if complete else f"{done}/{total}")
        badge.setStyleSheet(
            "color: %s; font-size: 11px; font-weight: 600; background: transparent; "
            "padding: 2px 8px; border-radius: 10px; border: 1px solid %s;"
            % ("#4caf50" if complete else "#808098", "#2d5c34" if complete else "#3a3a50")
        )
        head.addWidget(badge)

        del_cl = QPushButton("✕")
        del_cl.setFixedSize(24, 24)
        del_cl.setCursor(Qt.CursorShape.PointingHandCursor)
        del_cl.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 12px; "
            "color: #606080; font-size: 12px; }"
            "QPushButton:hover { background: #f44336; color: #fff; }"
        )
        del_cl.clicked.connect(lambda checked, cid=cl.id: self._delete_checklist(cid))
        head.addWidget(del_cl)
        v.addLayout(head)

        # ── 小项（勾选框 + 内容 + 删除） ──
        for it in items:
            v.addLayout(self._make_item_row(it))

        # ── + 添加项目 ──
        add_item = QPushButton("+ 添加项目")
        add_item.setStyleSheet(
            "QPushButton { background: transparent; border: 1px dashed #3a3a50; border-radius: 6px; "
            "padding: 5px; color: #606080; font-size: 11px; }"
            "QPushButton:hover { border-color: #7c5cfc; color: #7c5cfc; }"
        )
        add_item.setCursor(Qt.CursorShape.PointingHandCursor)
        add_item.clicked.connect(lambda checked, cid=cl.id: self._add_item(cid))
        v.addWidget(add_item)

        self._checklists_layout.addWidget(frame)

    def _make_item_row(self, it) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)

        cb = QCheckBox()
        cb.setChecked(bool(it.done))
        cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.setStyleSheet(
            "QCheckBox { spacing: 8px; background: transparent; }"
            "QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #5a5a7a; "
            "border-radius: 4px; background: #1e1e34; }"
            "QCheckBox::indicator:hover { border-color: #7c5cfc; }"
            "QCheckBox::indicator:checked { background: #4caf50; border-color: #4caf50; }"
        )
        cb.toggled.connect(lambda checked, iid=it.id: self._toggle_item(iid, checked))
        row.addWidget(cb)

        edit = QLineEdit(it.content)
        edit.setPlaceholderText("新项目")
        f = edit.font()
        f.setStrikeOut(bool(it.done))
        edit.setFont(f)
        edit.setStyleSheet(
            "QLineEdit { background: transparent; border: none; color: #e0e0e8; "
            "font-size: 13px; padding: 2px; }"
        )
        edit.editingFinished.connect(
            lambda e=edit, iid=it.id: self._save_item(iid, e.text())
        )
        row.addWidget(edit, stretch=1)

        del_item = QPushButton("✕")
        del_item.setFixedSize(20, 20)
        del_item.setCursor(Qt.CursorShape.PointingHandCursor)
        del_item.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 10px; "
            "color: #606080; font-size: 10px; }"
            "QPushButton:hover { background: #f44336; color: #fff; }"
        )
        del_item.clicked.connect(lambda checked, iid=it.id: self._delete_item(iid))
        row.addWidget(del_item)

        return row

    def _add_checklist(self):
        if not self._repo:
            return
        self._repo.add_checklist(self._task_id)
        self._rebuild_checklists()

    def _save_checklist_title(self, cl_id: int, text: str):
        if not self._repo:
            return
        self._repo.update_checklist_title(cl_id, text.strip() or "清单")

    def _delete_checklist(self, cl_id: int):
        try:
            self._repo.delete_checklist(cl_id)
        except Exception as e:
            print(f"删除清单失败: {e}")
        self._rebuild_checklists()

    def _add_item(self, cl_id: int):
        if not self._repo:
            return
        self._repo.add_checklist_item(cl_id)
        self._rebuild_checklists()

    def _save_item(self, item_id: int, text: str):
        if not self._repo:
            return
        self._repo.update_checklist_item(item_id, text)

    def _toggle_item(self, item_id: int, checked: bool):
        """勾选/取消勾选小项 → 刷新（全部勾选时清单外部标记为已完成）. """
        if not self._repo:
            return
        try:
            self._repo.set_checklist_item_done(item_id, bool(checked))
        except Exception as e:
            print(f"勾选清单小项失败: {e}")
        self._rebuild_checklists()

    def _delete_item(self, item_id: int):
        try:
            self._repo.delete_checklist_item(item_id)
        except Exception as e:
            print(f"删除清单小项失败: {e}")
        self._rebuild_checklists()

    # ── 评论 ──────────────────────────────────────────

    def _rebuild_comments(self):
        self._clear_layout(self._comments_layout)
        if not self._task or not self._repo:
            return
        for c in self._repo.get_comments(self._task_id):
            self._add_comment_widget(c)

    def _add_comment_widget(self, c):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: #22223a; border: 1px solid #33334e; border-radius: 8px; }"
        )
        v = QVBoxLayout(frame)
        v.setContentsMargins(10, 8, 8, 4)
        v.setSpacing(4)

        # 作者 + 时间
        ts = c.created_at.strftime("%m/%d %H:%M") if c.created_at else ""
        head = QHBoxLayout()
        author = QLabel(f"<b>{c.author}</b>")
        author.setStyleSheet("color: #c0c0d0; font-size: 12px; background: transparent;")
        time_lbl = QLabel(ts)
        time_lbl.setStyleSheet("color: #606080; font-size: 11px; background: transparent;")
        head.addWidget(author)
        head.addSpacing(8)
        head.addWidget(time_lbl)
        head.addStretch()
        v.addLayout(head)

        # 内容 / 编辑态
        if self._editing_comment_id == c.id:
            edit_row = QHBoxLayout()
            edit_row.setSpacing(6)
            self._comment_edit = QLineEdit(c.content)
            self._comment_edit.setStyleSheet(
                "QLineEdit { padding: 6px 8px; border-radius: 6px; background: #1e1e34; "
                "color: #e0e0e8; border: 1px solid #7c5cfc; font-size: 13px; }"
            )
            save_btn = QPushButton("保存")
            save_btn.setStyleSheet(
                "QPushButton { background: #7c5cfc; border: none; border-radius: 6px; "
                "padding: 6px 12px; color: #fff; font-size: 11px; }"
                "QPushButton:hover { background: #6a4acc; }"
            )
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.clicked.connect(lambda checked, cid=c.id: self._save_comment_edit(cid))
            cancel_btn = QPushButton("取消")
            cancel_btn.setStyleSheet(
                "QPushButton { background: transparent; border: 1px solid #3a3a50; border-radius: 6px; "
                "padding: 6px 12px; color: #a0a0b8; font-size: 11px; }"
                "QPushButton:hover { border-color: #5a5a7a; }"
            )
            cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cancel_btn.clicked.connect(lambda checked: self._cancel_comment_edit())
            edit_row.addWidget(self._comment_edit, stretch=1)
            edit_row.addWidget(save_btn)
            edit_row.addWidget(cancel_btn)
            v.addLayout(edit_row)
        else:
            content = QLabel(c.content)
            content.setWordWrap(True)
            content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            content.setStyleSheet("color: #e0e0e8; font-size: 13px; background: transparent;")
            v.addWidget(content)

        # 右下角 ⋮（编辑 / 删除）
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        dots = QPushButton("⋮")
        dots.setFixedSize(22, 22)
        dots.setCursor(Qt.CursorShape.PointingHandCursor)
        dots.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 5px; "
            "color: #606080; font-size: 14px; }"
            "QPushButton:hover { background: #3a3a5a; color: #e0e0e8; }"
        )
        dots.clicked.connect(lambda checked, cid=c.id: self._show_comment_menu(dots, cid))
        btn_row.addWidget(dots)
        v.addLayout(btn_row)

        self._comments_layout.addWidget(frame)

    def _show_comment_menu(self, btn: QPushButton, comment_id: int):
        """⋮ 点击 → 右下角展开编辑/删除小卡片."""
        card = _CommentActionsCard(
            on_edit=lambda: self._start_edit_comment(comment_id),
            on_delete=lambda: self._delete_comment(comment_id),
            parent=self,
        )
        card.move(btn.mapToGlobal(QPoint(0, btn.height() + 2)))
        card.show()

    def _start_edit_comment(self, comment_id: int):
        self._editing_comment_id = comment_id
        self._rebuild_comments()

    def _save_comment_edit(self, comment_id: int):
        text = self._comment_edit.text().strip() if self._comment_edit else ""
        if text:
            try:
                self._repo.update_comment(comment_id, text)
            except Exception as e:
                print(f"编辑评论失败: {e}")
        self._editing_comment_id = None
        self._rebuild_comments()

    def _cancel_comment_edit(self):
        self._editing_comment_id = None
        self._rebuild_comments()

    def _delete_comment(self, comment_id: int):
        try:
            self._repo.delete_comment(comment_id)
        except Exception as e:
            print(f"删除评论失败: {e}")
        self._editing_comment_id = None
        self._rebuild_comments()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ── 操作 ──────────────────────────────────────────

    def _save_title(self):
        self._repo.update_task_title(self._task_id, self._title_edit.text())

    def _save_dates(self):
        end = self._end_date.date()
        start = self._start_date.date()
        if end < start:
            end = start
        with self._repo.session() as s:
            from pulse.db.models import CalendarTask
            s.query(CalendarTask).filter(CalendarTask.id == self._task_id).update({"end_date": end})

    # ── 定时提醒 ────────────────────────────────────────

    def _on_remind_type_changed(self, idx: int):
        """普通任务 / 定时提醒 切换时显示或隐藏时间选择."""
        is_remind = idx == 1
        self._remind_date.setVisible(is_remind)
        self._remind_time.setVisible(is_remind)
        if is_remind:
            self._save_reminder()
        else:
            self._repo.set_task_reminder(self._task_id, None)

    def _save_reminder(self):
        """保存提醒时间（本地时间）. """
        if not self._task_id or not self._repo:
            return
        if self._remind_type.currentIndex() != 1:
            return
        remind_at = datetime.combine(self._remind_date.date(), self._remind_time.time().toPyTime())
        self._repo.set_task_reminder(self._task_id, remind_at)

    def _add_field(self):
        f = self._repo.add_task_field(self._task_id)
        self._rebuild_fields()
        # 滚动到底部
        # (QScrollArea 会在 re-layout 时自动处理)

    def _post_comment(self):
        text = self._comment_input.text().strip()
        if text:
            self._repo.add_comment(self._task_id, text)
            self._comment_input.clear()
            self._rebuild_comments()

    def _delete_task(self):
        self._repo.delete_task(self._task_id)
        self.accept()
