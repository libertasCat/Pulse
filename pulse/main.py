"""Pulse 入口 —— CLI 追踪模式 / GUI 桌面模式."""

import logging
import signal
import sys
import threading
import time
from datetime import date
from typing import Optional

from pulse.core.tracker import AppTracker, TrackerConfig
from pulse.db.repository import Repository
from pulse.ui.theme import ThemeManager, ThemeMode
from pulse.utils.config import ConfigManager
from pulse.utils.constants import DB_PATH

logger = logging.getLogger("pulse")


# ── 日志 ──────────────────────────────────────────────────


def setup_logging() -> None:
    """配置日志：同时输出到文件和控制台."""
    from pulse.utils.constants import DATA_DIR
    log_file = DATA_DIR / "pulse.log"
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(
        level=logging.DEBUG,
        format=fmt,
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


# ── 全局对象（GUI 与 CLI 共享） ────────────────────────────

_config_mgr: Optional[ConfigManager] = None
_repo: Optional[Repository] = None
_tracker: Optional[AppTracker] = None


def _init_backend() -> None:
    """初始化配置、数据库、追踪器（CLI 和 GUI 共用）. """
    global _config_mgr, _repo, _tracker

    _config_mgr = ConfigManager()
    cfg = _config_mgr.config

    _repo = Repository(str(DB_PATH))
    _repo.initialize_db()

    tracker_config = TrackerConfig(
        poll_interval=cfg.tracker.poll_interval,
        idle_threshold=cfg.tracker.idle_threshold,
    )
    _tracker = AppTracker(tracker_config, _repo)
    _tracker.start()


# ── CLI 追踪模式 ─────────────────────────────────────────


def run_tracker() -> None:
    """CLI 模式 —— 仅运行追踪引擎，后台打印状态."""
    setup_logging()
    _print_banner()
    _init_backend()
    assert _tracker is not None

    shutdown = threading.Event()

    # 信号处理
    if sys.platform == "win32":
        def handler(sig, frame):
            logger.info("收到退出信号，正在关闭...")
            shutdown.set()
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
    else:
        signal.signal(signal.SIGINT, lambda s, f: shutdown.set())
        signal.signal(signal.SIGTERM, lambda s, f: shutdown.set())

    # 主循环
    try:
        while not shutdown.is_set():
            time.sleep(5)
            today = date.today()
            total = _repo.get_total_duration_by_date(today)
            if _tracker and _tracker.current_session:
                cur = _tracker.current_session
                status = (f"\r[Pulse] 今日已追踪: {total // 60} 分 {total % 60} 秒  |  "
                          f"当前: {cur.process_name}  ({cur.duration_seconds}s)")
            else:
                status = f"\r[Pulse] 今日已追踪: {total // 60} 分 {total % 60} 秒"
            print(status, end="", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        print()
        _shutdown()


# ── GUI 桌面模式 ─────────────────────────────────────────


def run_gui() -> None:
    """GUI 模式 —— 启动 PyQt6 桌面界面."""
    from PyQt6.QtWidgets import QApplication

    setup_logging()
    _print_banner()

    # 创建 QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("Pulse")
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口不退出，保留托盘

    # 初始化后端
    _init_backend()
    assert _repo is not None
    assert _tracker is not None
    assert _config_mgr is not None

    # 主题
    theme = ThemeManager.instance()
    mode_str = _config_mgr.config.theme
    theme.set_mode(ThemeMode(mode_str) if mode_str in ("dark", "light") else ThemeMode.SYSTEM)
    theme.apply()

    # 主窗口
    from pulse.ui.main_window import MainWindow
    from pulse.ui.tray_icon import TrayIcon

    window = MainWindow(
        tracker=_tracker,
        repo=_repo,
        config_mgr=_config_mgr,
    )

    # 托盘
    tray = TrayIcon(window)
    tray.show()

    # 互相关联
    window.set_tray_icon(tray)
    window.show()

    # 退出时清理
    app.aboutToQuit.connect(_shutdown)

    sys.exit(app.exec())


# ── 公共方法 ─────────────────────────────────────────────


def _print_banner() -> None:
    logger.info("=" * 50)
    logger.info("Pulse v%s  启动", "0.1.0")
    logger.info("数据目录: %s", DB_PATH.parent)
    logger.info("=" * 50)


def _shutdown() -> None:
    """安全关闭：停止追踪器 + 保存配置."""
    global _tracker, _config_mgr
    if _tracker:
        _tracker.stop()
    if _config_mgr:
        _config_mgr.save()
    logger.info("Pulse 已安全退出")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "cli"
    if mode in ("gui", "--gui"):
        run_gui()
    else:
        run_tracker()
