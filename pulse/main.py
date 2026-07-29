"""Pulse 入口 —— 初始化和启动追踪器."""

import logging
import signal
import sys
import threading
import time
from datetime import date

from pulse.core.tracker import AppTracker, TrackerConfig
from pulse.db.repository import Repository
from pulse.utils.config import ConfigManager
from pulse.utils.constants import DB_PATH

logger = logging.getLogger("pulse")


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


def run_tracker() -> None:
    """仅运行追踪引擎（无 GUI 模式），用于调试/验证."""
    setup_logging()
    logger.info("=" * 50)
    logger.info("Pulse v%s  启动", "0.1.0")
    logger.info("数据目录: %s", DB_PATH.parent)
    logger.info("=" * 50)

    # 加载配置
    cfg_mgr = ConfigManager()
    cfg = cfg_mgr.config

    # 初始化数据库
    repo = Repository(str(DB_PATH))
    repo.initialize_db()
    logger.info("数据库已初始化")

    # 创建并启动追踪器
    tracker_config = TrackerConfig(
        poll_interval=cfg.tracker.poll_interval,
        idle_threshold=cfg.tracker.idle_threshold,
    )
    tracker = AppTracker(tracker_config, repo)
    tracker.on_session_flushed = lambda s: None  # 可在此处添加回调

    # ── 信号处理 ──
    shutdown_requested = threading.Event()
    if sys.platform == "win32":
        # Windows 上用 SetConsoleCtrlHandler 捕获 Ctrl+C
        def handler(sig, frame):
            logger.info("收到退出信号，正在关闭...")
            shutdown_requested.set()
        signal.signal(signal.SIGINT, handler)
        signal.signal(signal.SIGTERM, handler)
    else:
        signal.signal(signal.SIGINT, lambda s, f: shutdown_requested.set())
        signal.signal(signal.SIGTERM, lambda s, f: shutdown_requested.set())

    # 启动追踪
    tracker.start()

    # 主线程定期打印状态摘要
    try:
        while not shutdown_requested.is_set():
            time.sleep(5)
            today = date.today()
            total = repo.get_total_duration_by_date(today)
            if tracker.current_session:
                cur = tracker.current_session
                status = (f"\r[Pulse] 今日已追踪: {total // 60} 分 {total % 60} 秒  |  "
                          f"当前: {cur.process_name}  ({cur.duration_seconds}s)")
            else:
                status = f"\r[Pulse] 今日已追踪: {total // 60} 分 {total % 60} 秒"
            print(status, end="", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        print()
        tracker.stop()
        cfg_mgr.save()
        logger.info("Pulse 已安全退出")

        # 打印今日摘要
        today = date.today()
        total = repo.get_total_duration_by_date(today)
        top_apps = repo.get_usage_summary_by_date(today, "process_name")[:5]
        print("\n[Pulse] 今日使用摘要:")
        print(f"   总活跃时长: {total // 60} 分 {total % 60} 秒")
        print("   Top 应用:")
        for app in top_apps:
            mins = app["total_seconds"] // 60
            secs = app["total_seconds"] % 60
            print(f"     {app['name']:<20}  {mins:>4} 分 {secs:>2} 秒")


def run_gui() -> None:
    """启动 PyQt6 图形界面（预留，后续实现）."""
    raise NotImplementedError("GUI 模式尚未实现")


if __name__ == "__main__":
    run_tracker()
