"""任务详情模态对话框 —— Notion 风格，屏幕中央弹出."""

from datetime import date, datetime
from typing import Optional

from PyQt6.QtCore import Qt  # type: ignore
from PyQt6.QtWidgets import (  # type: ignore
    QDateEdit, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QScrollArea, QTextEdit,
    QVBoxLayout, QWidget,
)

from pulse.db.repository import Repository


class TaskDetailDialog(QDialog):
    """屏幕中央出现的 Notion 风格任务详情卡片."""

    def __init__(self, task_id: int, repo: Repository, parent=None):
        super().__init__(parent)
        self._task_id = task_id
        self._repo = repo
        self._task = repo.get_task_by_id(task_id)

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
        inner_lo.setContentsMargins(24, 20, 24, 20)
        inner_lo.setSpacing(12)
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
        self._start_date = QDateEdit(self._task.date)
        self._start_date.setCalendarPopup(True)
        self._start_date.setStyleSheet(
            "QDateEdit { padding: 4px 8px; border-radius: 6px; background: #25253a; "
            "color: #e0e0e8; border: 1px solid #3a3a50; font-size: 12px; }"
            "QDateEdit:focus { border-color: #7c5cfc; }"
        )
        end_lbl = QLabel("结束")
        end_lbl.setStyleSheet("color: #808098; font-size: 12px; background: transparent;")
        self._end_date = QDateEdit(self._task.end_date or self._task.date)
        self._end_date.setCalendarPopup(True)
        self._end_date.setStyleSheet(
            "QDateEdit { padding: 4px 8px; border-radius: 6px; background: #25253a; "
            "color: #e0e0e8; border: 1px solid #3a3a50; font-size: 12px; }"
            "QDateEdit:focus { border-color: #7c5cfc; }"
        )
        self._end_date.dateChanged.connect(self._save_dates)
        date_row.addWidget(start_lbl)
        date_row.addWidget(self._start_date)
        date_row.addSpacing(12)
        date_row.addWidget(end_lbl)
        date_row.addWidget(self._end_date)
        date_row.addStretch()
        inner_lo.addLayout(date_row)

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
        self._fields_layout.setSpacing(6)
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

        # ── 评论 ──
        inner_lo.addWidget(self._mk_label("评论"))
        self._comments_layout = QVBoxLayout()
        self._comments_layout.setSpacing(6)
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

    @staticmethod
    def _mk_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 12px; color: #808098; margin-top: 4px; background: transparent;")
        return lbl

    # ── 字段 ──────────────────────────────────────────

    def _rebuild_fields(self):
        self._clear_layout(self._fields_layout)
        if not self._task:
            return
        for field in self._task.fields:
            self._add_field_widget(field.id, field.content)

    def _add_field_widget(self, fid: int, content: str):
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: #25253a; border: 1px solid #3a3a50; border-radius: 8px; "
            "padding: 2px; }"
            "QFrame:hover { border-color: #5a5a7a; }"
        )
        lo = QHBoxLayout(frame)
        lo.setContentsMargins(6, 4, 6, 4)

        edit = QTextEdit()
        edit.setPlainText(content)
        edit.setFixedHeight(52)
        edit.setStyleSheet(
            "QTextEdit { background: transparent; border: none; color: #e0e0e8; "
            "font-size: 13px; padding: 2px; }"
        )
        edit.textChanged.connect(lambda fid=fid, e=edit: self._repo.update_task_field(fid, e.toPlainText()))

        del_btn = QPushButton("✕")
        del_btn.setFixedSize(24, 24)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 12px; "
            "color: #606080; font-size: 12px; }"
            "QPushButton:hover { background: #f44336; color: #fff; }"
        )
        del_btn.clicked.connect(lambda fid=fid: (self._repo.delete_task_field(fid), self._rebuild_fields()))

        lo.addWidget(edit, stretch=1)
        lo.addWidget(del_btn)
        self._fields_layout.addWidget(frame)

    # ── 评论 ──────────────────────────────────────────

    def _rebuild_comments(self):
        self._clear_layout(self._comments_layout)
        if not self._task:
            return
        for c in self._repo.get_comments(self._task_id):
            ts = c.created_at.strftime("%m/%d %H:%M") if c.created_at else ""
            text = f"<b>{c.author}</b>  <span style='color:#606080;font-size:11px;'>{ts}</span><br>{c.content}"
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("font-size: 12px; padding: 6px 0; color: #c0c0d0; background: transparent;")
            self._comments_layout.addWidget(lbl)

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
        end = self._end_date.date().toPyDate()
        start = self._start_date.date().toPyDate()
        if end < start:
            end = start
        with self._repo.session() as s:
            from pulse.db.models import CalendarTask
            s.query(CalendarTask).filter(CalendarTask.id == self._task_id).update({"end_date": end})

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
