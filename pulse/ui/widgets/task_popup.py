"""任务创建弹出卡 —— 浮在日历上层的简洁卡片."""

from typing import Optional

from PyQt6.QtCore import Qt, QTimer  # type: ignore
from PyQt6.QtWidgets import (  # type: ignore
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)


class TaskCreatePopup(QFrame):
    """浮动在日历上的任务创建卡片."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("taskPopup")
        # 用 Tool 替代 Popup：Popup 窗口在 Windows 上输入法(IME)支持有问题
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.setFixedSize(280, 140)
        self.setStyleSheet(
            "QFrame#taskPopup { background: #25253a; border: 1px solid #4a4a6a; "
            "border-radius: 12px; }"
        )

        lo = QVBoxLayout(self)
        lo.setContentsMargins(16, 14, 16, 14)
        lo.setSpacing(8)

        lo.addWidget(QLabel("新建任务", styleSheet="font-size: 14px; font-weight: 700; color: #fff; background: transparent;"))

        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("任务标题...")
        self._title_input.setStyleSheet(
            "QLineEdit { padding: 8px; border-radius: 6px; background: #1e1e34; "
            "color: #fff; border: 1px solid #3a3a50; font-size: 13px; }"
            "QLineEdit:focus { border-color: #7c5cfc; }"
        )
        self._title_input.setFocus()
        self._title_input.returnPressed.connect(self._confirm)
        lo.addWidget(self._title_input)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._cancel_btn = QPushButton("取消")
        self._cancel_btn.setStyleSheet(
            "QPushButton { background: #3a3a5a; border: none; border-radius: 6px; "
            "padding: 6px 16px; color: #a0a0b8; font-size: 12px; }"
            "QPushButton:hover { background: #4a4a6a; }"
        )
        self._cancel_btn.clicked.connect(self.close)
        btn_row.addWidget(self._cancel_btn)

        self._create_btn = QPushButton("创建")
        self._create_btn.setStyleSheet(
            "QPushButton { background: #7c5cfc; border: none; border-radius: 6px; "
            "padding: 6px 20px; color: #fff; font-weight: 600; font-size: 12px; }"
            "QPushButton:hover { background: #6a4acc; }"
        )
        self._create_btn.clicked.connect(self._confirm)
        btn_row.addWidget(self._create_btn)

        lo.addLayout(btn_row)

        self._callback = None

    def show_at(self, x: int, y: int, callback):
        """在指定全局坐标弹出，callback 接收标题字符串."""
        self._callback = callback
        self._title_input.clear()
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
        # 使用 ActiveWindowFocusReason 建立输入法上下文
        self._title_input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)
        QTimer.singleShot(50, lambda: self._title_input.setFocus(Qt.FocusReason.ActiveWindowFocusReason))

    def set_callback(self, callback):
        self._callback = callback

    def _confirm(self):
        title = self._title_input.text().strip()
        if not title:
            return
        if self._callback:
            self._callback(title)
        self.close()
