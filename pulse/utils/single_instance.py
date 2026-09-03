"""跨平台单例运行保护 —— Windows 互斥体 / Unix 文件锁."""

import logging
import os
from typing import Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows 没有 fcntl
    fcntl = None  # type: ignore[assignment]

from pulse.utils.constants import DATA_DIR

logger = logging.getLogger(__name__)

_MUTEX_NAME = "Pulse-7c5cfc-Singleton"
_mutex_handle = None
_lock_file: Optional[object] = None


def ensure_single_instance() -> bool:
    """检查是否已有 Pulse 实例在运行.

    Windows 使用命名互斥体，Linux 和其他 Unix 系统使用 ``flock``。
    Unix 文件锁会在进程异常退出时由操作系统自动释放，不会产生失效锁。
    """

    global _mutex_handle, _lock_file
    if os.name != "nt" and fcntl is not None:
        if _lock_file is not None:
            logger.warning("当前进程已经持有 Pulse 单例锁")
            return False
        try:
            lock_path = DATA_DIR / "pulse.lock"
            _lock_file = open(lock_path, "a+", encoding="utf-8")
            fcntl.flock(_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (OSError, IOError):
            if _lock_file:
                _lock_file.close()
                _lock_file = None
            logger.warning("检测到已有 Pulse 实例在运行")
            return False

    try:
        import win32api
        import win32event
        import winerror

        _mutex_handle = win32event.CreateMutex(None, False, _MUTEX_NAME)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            logger.warning("检测到已有 Pulse 实例在运行")
            return False
        return True
    except ImportError:
        logger.warning("pywin32 不可用，无法执行 Windows 单例检查")
        return True
    except Exception as exc:
        logger.warning("单例检查失败，跳过: %s", exc)
        return True


def release_singleton() -> None:
    """释放单例锁（程序退出时调用）."""

    global _mutex_handle, _lock_file
    if _lock_file and fcntl is not None:
        try:
            fcntl.flock(_lock_file.fileno(), fcntl.LOCK_UN)
            _lock_file.close()
        except OSError:
            pass
        _lock_file = None
    if _mutex_handle:
        try:
            import win32event
            win32event.CloseHandle(_mutex_handle)
        except Exception:
            pass
        _mutex_handle = None
