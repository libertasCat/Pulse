"""Pulse 入口 —— CLI 追踪模式 / GUI 桌面模式."""

import logging
import signal
import sys
import threading
import time
from datetime import date
from typing import Optional

from pulse import __version__
from pulse.core.tracker import AppTracker, TrackerConfig
from pulse.db.repository import Repository
from pulse.ui.theme import ThemeManager, ThemeMode
from pulse.utils.config import ConfigManager
from pulse.utils.constants import DB_PATH
from pulse.utils.single_instance import ensure_single_instance, release_singleton

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

    if not ensure_single_instance():
        logger.error("Pulse 已在运行中，请勿重复启动")
        print("[Pulse] 错误: Pulse 已在运行中，请勿重复启动")
        sys.exit(1)

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

    if not ensure_single_instance():
        logger.error("Pulse 已在运行中，请勿重复启动")
        print("[Pulse] 错误: Pulse 已在运行中，请勿重复启动")
        sys.exit(1)

    # 创建 QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("Pulse")
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口不退出，保留托盘

    # 初始化后端
    _init_backend()
    assert _repo is not None
    assert _tracker is not None
    assert _config_mgr is not None

    # 定期数据清理（每天运行一次，默认保留 180 天）
    from PyQt6.QtCore import QTimer as _QTimer
    _cleanup_timer = _QTimer()
    _cleanup_timer.timeout.connect(lambda: _repo.cleanup_old_data(180))
    _cleanup_timer.start(86400000)  # 24h
    _repo.cleanup_old_data(180)  # 启动时立刻清理一次

    # AI 自动分类（每小时运行一次，只处理热门未分类应用）
    if _config_mgr.config.llm.enabled:
        from pulse.core.classifier import ClassifierService as _ClassifierService
        _classifier = _ClassifierService(_repo, _config_mgr.config.llm)
        _classifier.auto_classify()  # 启动时分类一次
        _classify_timer = _QTimer()
        _classify_timer.timeout.connect(_classifier.auto_classify)
        _classify_timer.start(3600000)  # 每小时

    # 任务定时提醒（每分钟检查一次到期任务并发送邮件）
    _remind_timer = _QTimer()
    _remind_timer.timeout.connect(lambda: _check_reminders(_repo, _config_mgr))
    _remind_timer.start(60000)  # 每分钟
    _check_reminders(_repo, _config_mgr)  # 启动时立即检查

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


def _check_reminders(repo: Repository, config_mgr: ConfigManager) -> None:
    """检查到期的定时任务并发送提醒邮件."""
    email_cfg = config_mgr.config.email
    if not email_cfg.enabled or not email_cfg.sender:
        return
    try:
        from pulse.services.email_sender import EmailConfig, send_email
        due = repo.get_due_reminders()
        if not due:
            return
        cfg = EmailConfig(
            sender=email_cfg.sender,
            auth_code=email_cfg.auth_code,
            recipient=email_cfg.recipient,
        )
        for task in due:
            subject = f"【Pulse 提醒】{task.title}"
            content = (
                f"任务：{task.title}\n"
                f"日期：{task.date.isoformat()}"
                + (f" ~ {task.end_date.isoformat()}" if task.end_date else "")
                + "\n\n这是来自 Pulse 的定时任务提醒。"
            )
            ok, err = send_email(cfg, subject, content)
            if ok:
                repo.mark_task_reminded(task.id)
                logger.info("已发送任务提醒: %s", task.title)
            else:
                logger.warning("任务提醒发送失败 [%s]: %s", task.title, err)
    except Exception as e:
        logger.error("提醒检查异常: %s", e)


def _print_banner() -> None:
    logger.info("=" * 50)
    logger.info("Pulse v%s  启动", __version__)
    logger.info("数据目录: %s", DB_PATH.parent)
    logger.info("=" * 50)


def _shutdown() -> None:
    """安全关闭：停止追踪器 + 保存配置 + 释放单例锁."""
    global _tracker, _config_mgr
    if _tracker:
        _tracker.stop()
    if _config_mgr:
        _config_mgr.save()
    release_singleton()
    logger.info("Pulse 已安全退出")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "gui"
    if mode in ("cli", "--cli"):
        run_tracker()
    else:
        run_gui()
