"""Windows 命名互斥体 —— 确保程序单例运行."""

import logging
import sys

logger = logging.getLogger(__name__)

_MUTEX_NAME = "Pulse-7c5cfc-Singleton"
_mutex_handle = None


def ensure_single_instance() -> bool:
    """检查是否已有 Pulse 实例在运行。

    Returns:
        True  → 当前是唯一实例，可以继续启动
        False → 已有实例在运行，当前进程应退出
    """
    global _mutex_handle
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
        # 非 Windows 或 pywin32 不可用，跳过检查
        return True
    except Exception as exc:
        logger.warning("单例检查失败，跳过: %s", exc)
        return True


def release_singleton() -> None:
    """释放互斥体（程序退出时调用）. """
    global _mutex_handle
    if _mutex_handle:
        try:
            import win32event
            win32event.CloseHandle(_mutex_handle)
        except Exception:
            pass
        _mutex_handle = None
