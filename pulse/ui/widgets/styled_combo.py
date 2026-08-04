"""主题感知的 QComboBox —— 弹出下拉列表时强制暗色样式，避免文字与背景同色."""

from PyQt6.QtWidgets import QComboBox


class StyledCombo(QComboBox):
    """QComboBox 子类 —— 弹出时注入暗色样式（与主题模式下拉框同款）. """

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
