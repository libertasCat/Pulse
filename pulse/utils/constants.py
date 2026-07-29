"""系统常量定义."""

import os
from pathlib import Path

# 数据存储路径
DATA_DIR = Path(os.path.expanduser("~")) / ".pulse"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 数据库
DB_PATH = DATA_DIR / "pulse.db"

# 默认追踪设置
DEFAULT_POLL_INTERVAL = 1.0       # 轮询间隔（秒）
DEFAULT_IDLE_THRESHOLD = 300       # 空闲判定阈值（秒，5分钟无操作）

# 已知浏览器列表
KNOWN_BROWSERS = {
    "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
    "opera.exe", "vivaldi.exe", "tor.exe", "iexplore.exe",
}

# 浏览器窗口标题后缀（用于提取页面标题）
BROWSER_TITLE_SUFFIXES = [
    " - Google Chrome",
    " - Microsoft Edge",
    " - Mozilla Firefox",
    " - Brave",
    " - Opera",
    " - Vivaldi",
    " - Internet Explorer",
]

# 各浏览器窗口标题分隔符
BROWSER_TITLE_SEPARATORS = [
    (" - ", " - Google Chrome"),
    (" - ", " - Microsoft Edge"),
    (" - ", " - Mozilla Firefox"),
    (" - ", " - Brave"),
    (" - ", " - Opera"),
    (" - ", " - Vivaldi"),
    (" | ", " - Mozilla Firefox"),
]

# 默认分类预设
DEFAULT_CATEGORIES = [
    {"name": "开发与设计", "color": "#4CAF50", "icon": "💻"},
    {"name": "办公与效率", "color": "#2196F3", "icon": "📋"},
    {"name": "浏览器", "color": "#FF9800", "icon": "🌐"},
    {"name": "社交与通讯", "color": "#E91E63", "icon": "💬"},
    {"name": "娱乐与影音", "color": "#9C27B0", "icon": "🎮"},
    {"name": "学习与阅读", "color": "#00BCD4", "icon": "📚"},
    {"name": "系统与工具", "color": "#607D8B", "icon": "⚙️"},
    {"name": "其他", "color": "#9E9E9E", "icon": "📦"},
]
