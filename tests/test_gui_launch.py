"""GUI 快速启动测试（offscreen 模式）."""

import os, sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from pulse.ui.theme import ThemeManager, ThemeMode
from pulse.ui.main_window import MainWindow
from pulse.ui.tray_icon import TrayIcon
import pulse.main as pm

app = QApplication(sys.argv)
app.setApplicationName("Pulse")
app.setQuitOnLastWindowClosed(False)

# 初始化后端（数据库 + 追踪器）
pm._init_backend()
assert pm._repo is not None
assert pm._tracker is not None

# 主题
theme = ThemeManager.instance()
mode_str = pm._config_mgr.config.theme
theme.set_mode(
    ThemeMode(mode_str) if mode_str in ("dark", "light") else ThemeMode.SYSTEM
)
theme.apply()

# 窗口 + 托盘
window = MainWindow(tracker=pm._tracker, repo=pm._repo, config_mgr=pm._config_mgr)
tray = TrayIcon(window)
tray.show()
window.set_tray_icon(tray)
window.show()

# 2 秒后退出
QTimer.singleShot(2000, app.quit)
app.exec()

pm._shutdown()
print("GUI 启动测试通过")
