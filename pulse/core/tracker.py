"""应用追踪引擎 —— 后台轮询活跃窗口并记录使用数据."""

import ctypes
import ctypes.wintypes
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable

import psutil
import win32api
import win32gui
import win32process

from pulse.db.models import AppSession
from pulse.db.repository import Repository
from pulse.utils.constants import KNOWN_BROWSERS, BROWSER_TITLE_SUFFIXES

logger = logging.getLogger(__name__)


# ─── Windows idle detection via ctypes ──────────────────────────

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.UINT),
        ("dwTime", ctypes.wintypes.DWORD),
    ]


def _get_idle_seconds() -> int:
    """获取自上次用户输入以来的空闲秒数（Windows 全局）.使用 GetLastInputInfo API."""
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        logger.warning("GetLastInputInfo 调用失败")
        return 0
    current_tick = kernel32.GetTickCount()
    elapsed = (ctypes.c_uint32(current_tick - info.dwTime).value) / 1000.0
    return int(elapsed)


# ─── 数据结构 ──────────────────────────────────────────────────


@dataclass
class WindowInfo:
    """当前活跃窗口的快照."""
    process_name: str = ""
    window_title: str = ""
    pid: int = 0


@dataclass
class TrackerConfig:
    """追踪引擎配置."""
    poll_interval: float = 1.0          # 轮询间隔（秒）
    idle_threshold: int = 300           # 空闲判定阈值（秒）
    excluded_processes: tuple = field(default_factory=tuple)  # 排除追踪的进程


# ─── 追踪引擎 ──────────────────────────────────────────────────


class AppTracker:
    """后台窗口追踪引擎.

    工作方式：
    1. 每秒轮询一次当前活跃窗口
    2. 同窗口持续使用 → 合并为一条会话记录（累加时长）
    3. 切换窗口 / 切入空闲 → Flush 当前会话，写入 DB
    4. 浏览器窗口自动提取页面标题
    """

    def __init__(self, config: TrackerConfig, repository: Repository):
        self.config = config
        self.repo = repository
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 当前正在累积的会话（尚未写入 DB）
        self._current: Optional[AppSession] = None
        self._session_epoch: Optional[float] = None  # time.time() of session start

        # ── 回调（可选） ──
        # 每次某段会话结束时触发，形参是刚写入 DB 的 AppSession
        self.on_session_flushed: Optional[Callable[[AppSession], None]] = None

    # ── 生命周期 ────────────────────────────────────────────

    def start(self) -> None:
        """启动追踪器（阻塞直到后台线程就绪）."""
        if self._running:
            logger.warning("追踪器已在运行中")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="AppTracker")
        # 使用 Event 确保线程已启动完毕
        started = threading.Event()
        self._thread.start()
        logger.info("追踪器已启动  |  轮询间隔=%ss  空闲阈值=%ss", self.config.poll_interval, self.config.idle_threshold)

    def stop(self) -> None:
        """停止追踪器并刷新最后一段会话."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._flush_current()
        logger.info("追踪器已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_session(self) -> Optional[AppSession]:
        """获取当前正在累积的会话（仅用于 UI 展示，非线程安全）.不用锁，用于外部只读查询。"""
        return self._current

    # ── 主循环 ─────────────────────────────────────────────

    def _run(self) -> None:
        """后台线程入口."""
        while self._running:
            try:
                window = self._get_active_window()
                idle_sec = _get_idle_seconds()
                is_idle = idle_sec >= self.config.idle_threshold

                self._update(window, is_idle)
            except Exception as exc:
                logger.error("追踪器主循环异常: %s", exc, exc_info=True)
            time.sleep(self.config.poll_interval)

    def _update(self, window: WindowInfo, is_idle: bool) -> None:
        """核心决策：是否需要切换会话."""
        with self._lock:
            if self._current is None:
                self._start_session(window, is_idle)
                return

            # 判断是否需要 flush
            if self._should_flush(window, is_idle):
                self._flush_current()
                self._start_session(window, is_idle)
            else:
                self._extend_session()

    def _should_flush(self, window: WindowInfo, is_idle: bool) -> bool:
        # 空闲状态变化 → flush
        if self._current.is_idle != is_idle:
            return True
        # 非空闲时，窗口变化 → flush
        if not is_idle and (
            self._current.process_name != window.process_name
            or self._current.window_title != window.window_title
        ):
            return True
        return False

    def _start_session(self, window: WindowInfo, is_idle: bool) -> None:
        now = time.time()
        browser_page = self._extract_browser_page(window) if not is_idle else None
        self._current = AppSession(
            process_name=window.process_name,
            window_title=window.window_title,
            browser_page=browser_page,
            start_time=datetime.fromtimestamp(now),
            duration_seconds=0,
            is_idle=is_idle,
        )
        self._session_epoch = now

    def _extend_session(self) -> None:
        """延长当前会话 —— 更新 duration 为从开始到现在的总时长."""
        delta = int(time.time() - self._session_epoch)
        self._current.duration_seconds = max(0, delta)

    def _flush_current(self) -> None:
        """将当前会话写入数据库并重置状态."""
        if self._current is None:
            return

        # 跳过过短的会话（< 1 秒，一般只是用户快速切换窗口时产生的噪声）
        if self._current.duration_seconds < 1:
            self._current = None
            self._session_epoch = None
            return

        now = time.time()
        self._current.end_time = datetime.fromtimestamp(now)

        try:
            saved = self.repo.save_session(self._current)
            if self.on_session_flushed:
                self.on_session_flushed(saved)
            logger.debug("会话已保存: [%s] %s  %ds", saved.process_name, saved.window_title, saved.duration_seconds)
        except Exception as exc:
            logger.error("写入数据库失败: %s", exc)

        self._current = None
        self._session_epoch = None

    # ── 窗口信息采集 ─────────────────────────────────────────

    @staticmethod
    def _get_active_window() -> WindowInfo:
        """获取当前前台窗口的信息.

        Returns:
            WindowInfo: 包含进程名、窗口标题、PID
        """
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return WindowInfo(process_name="unknown", window_title="", pid=0)

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            title = win32gui.GetWindowText(hwnd) or ""

            # 通过 psutil 获取进程名
            try:
                proc = psutil.Process(pid)
                process_name = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                process_name = "unknown"

            return WindowInfo(process_name=process_name, window_title=title, pid=pid)
        except Exception as exc:
            logger.warning("获取窗口信息失败: %s", exc)
            return WindowInfo(process_name="error", window_title="", pid=0)

    # ── 浏览器页面识别 ────────────────────────────────────────

    @staticmethod
    def _extract_browser_page(window: WindowInfo) -> Optional[str]:
        """从浏览器窗口标题中提取实际页面标题.

        Chrome/Edge 窗口标题格式: "页面标题 - Google Chrome"
        Firefox 可能用 " | " 分割域名:  "页面标题 | 站点名 - Mozilla Firefox"
        新标签页 / 设置页等无意义标题返回 None.
        """
        proc = window.process_name.lower()
        if proc not in KNOWN_BROWSERS:
            return None

        title = window.window_title.strip()
        if not title or title.startswith("http"):
            return None

        # 尝试移除已知的浏览器后缀
        cleaned = title
        for suffix in BROWSER_TITLE_SUFFIXES:
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)].strip()
                break

        # 对新标签页等无意义的标题返回 None
        meaningless = {
            "new tab", "新标签页", "about:blank", "settings",
            "设置", "extensions", "扩展程序", "bookmarks", "书签管理器",
            "history", "历史记录", "downloads", "下载",
        }
        if cleaned.lower() in meaningless:
            return None

        # 排除空标题和纯分隔符
        if not cleaned or cleaned in ("-", "|"):
            return None

        return cleaned

    # ── 辅助 ─────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """获取当前追踪器的简要统计信息."""
        with self._lock:
            return {
                "running": self._running,
                "current_session": (
                    {
                        "process_name": self._current.process_name,
                        "window_title": self._current.window_title,
                        "duration": self._current.duration_seconds,
                        "is_idle": self._current.is_idle,
                    }
                    if self._current
                    else None
                ),
            }
