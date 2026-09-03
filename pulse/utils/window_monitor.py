"""跨平台活动窗口和用户空闲状态采集.

Windows 使用 pywin32，Linux 优先使用 GNOME Wayland 的 D-Bus 接口，
并回退到 X11 的 ``xprop``。所有平台依赖都在实际使用时惰性导入，
因此 Linux 启动时不会因为缺少 Windows 模块而失败。
"""

from __future__ import annotations

import ast
import json
import logging
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional, Sequence

import psutil

logger = logging.getLogger(__name__)


@dataclass
class WindowInfo:
    """当前活动窗口的快照."""

    process_name: str = ""
    window_title: str = ""
    pid: int = 0
    available: bool = True


_ACTIVE_BACKEND_WARNING_SHOWN = False
_IDLE_BACKEND_WARNING_SHOWN = False
_GNOME_SHELL_EVAL_AVAILABLE: Optional[bool] = None
_MUTTER_IDLE_AVAILABLE: Optional[bool] = None


def get_active_window() -> WindowInfo:
    """获取当前活动窗口，无法访问桌面接口时返回不可用快照."""

    system = platform.system()
    if system == "Windows":
        return _get_windows_active_window()
    if system == "Linux":
        return _get_linux_active_window()

    _warn_backend_unavailable(f"暂不支持 {system} 的活动窗口采集")
    return WindowInfo(available=False)


def get_idle_seconds() -> int:
    """获取自上次用户输入以来的空闲秒数.

    Linux 桌面不一定提供统一的跨桌面 API。无法取得空闲时间时返回 0，
    这样不会误把正在使用的电脑当成空闲；同时会记录一次可操作的警告。
    """

    system = platform.system()
    if system == "Windows":
        return _get_windows_idle_seconds()
    if system == "Linux":
        return _get_linux_idle_seconds()

    _warn_backend_unavailable(f"暂不支持 {system} 的空闲检测", idle=True)
    return 0


# ── 通用辅助 ───────────────────────────────────────────────


def _run_command(args: Sequence[str], timeout: float = 0.6) -> Optional[str]:
    """安全执行桌面探测命令，失败时返回 None."""

    if not args or shutil.which(args[0]) is None:
        return None
    try:
        result = subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _process_window_info(pid: int, title: str) -> WindowInfo:
    """将 PID 和标题补全为应用快照."""

    if pid <= 0:
        return WindowInfo(process_name="unknown", window_title=title, pid=0, available=False)
    try:
        process_name = psutil.Process(pid).name() or "unknown"
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        process_name = "unknown"
    return WindowInfo(process_name=process_name, window_title=title, pid=pid)


def _warn_backend_unavailable(message: str, idle: bool = False) -> None:
    """只记录一次桌面后端不可用的警告，避免轮询日志刷屏."""

    global _ACTIVE_BACKEND_WARNING_SHOWN, _IDLE_BACKEND_WARNING_SHOWN
    if idle:
        already_shown = _IDLE_BACKEND_WARNING_SHOWN
    else:
        already_shown = _ACTIVE_BACKEND_WARNING_SHOWN
    if not already_shown:
        suffix = "；Pulse 将暂时跳过窗口记录" if not idle else ""
        logger.warning("%s%s", message, suffix)
        if idle:
            _IDLE_BACKEND_WARNING_SHOWN = True
        else:
            _ACTIVE_BACKEND_WARNING_SHOWN = True


# ── Windows ─────────────────────────────────────────────────


def _get_windows_active_window() -> WindowInfo:
    """通过 pywin32 获取 Windows 前台窗口."""

    try:
        import win32gui  # type: ignore
        import win32process  # type: ignore

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return WindowInfo(process_name="unknown", available=False)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        title = win32gui.GetWindowText(hwnd) or ""
        return _process_window_info(pid, title)
    except (ImportError, OSError, RuntimeError) as exc:
        logger.warning("Windows 窗口采集不可用: %s", exc)
        return WindowInfo(available=False)
    except Exception as exc:
        logger.warning("获取 Windows 活动窗口失败: %s", exc)
        return WindowInfo(available=False)


def _get_windows_idle_seconds() -> int:
    """通过 GetLastInputInfo 获取 Windows 全局空闲时间."""

    try:
        import ctypes
        import ctypes.wintypes

        class LastInputInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.wintypes.UINT),
                ("dwTime", ctypes.wintypes.DWORD),
            ]

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        info = LastInputInfo()
        info.cbSize = ctypes.sizeof(LastInputInfo)
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            logger.warning("GetLastInputInfo 调用失败")
            return 0
        current_tick = kernel32.GetTickCount()
        elapsed = (ctypes.c_uint32(current_tick - info.dwTime).value) / 1000.0
        return int(elapsed)
    except Exception as exc:
        logger.warning("Windows 空闲检测不可用: %s", exc)
        return 0


# ── Linux 活动窗口 ──────────────────────────────────────────


def _get_linux_active_window() -> WindowInfo:
    """获取 Linux 活动窗口，兼容 GNOME Wayland 和 X11."""

    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    backends = (
        (_get_gnome_wayland_active_window, _get_x11_active_window)
        if session_type == "wayland"
        else (_get_x11_active_window, _get_gnome_wayland_active_window)
    )

    for backend in backends:
        info = backend()
        if info is not None:
            return info

    _warn_backend_unavailable(
        "当前 Linux 桌面未提供活动窗口接口（Wayland 非 GNOME 或 X11 工具缺失）"
    )
    return WindowInfo(available=False)


def _get_gnome_wayland_active_window() -> Optional[WindowInfo]:
    """通过 GNOME Shell Eval 获取 Wayland 活动窗口."""

    global _GNOME_SHELL_EVAL_AVAILABLE
    if not os.environ.get("WAYLAND_DISPLAY"):
        return None
    if _GNOME_SHELL_EVAL_AVAILABLE is False:
        return None

    expression = (
        "(() => {"
        " const w = global.display.focus_window;"
        " return JSON.stringify({pid: w ? w.get_pid() : 0, "
        "title: w ? (w.get_title() || '') : ''});"
        "})()"
    )
    output = _run_command(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.gnome.Shell",
            "--object-path",
            "/org/gnome/Shell",
            "--method",
            "org.gnome.Shell.Eval",
            expression,
        ]
    )
    if output is None:
        _GNOME_SHELL_EVAL_AVAILABLE = False
        return None

    payload = _parse_gdbus_string(output)
    if payload is None:
        _GNOME_SHELL_EVAL_AVAILABLE = False
        return None
    try:
        data = json.loads(payload)
        _GNOME_SHELL_EVAL_AVAILABLE = True
        return _process_window_info(int(data.get("pid", 0)), str(data.get("title", "")))
    except (TypeError, ValueError, json.JSONDecodeError):
        _GNOME_SHELL_EVAL_AVAILABLE = False
        return None


def _get_x11_active_window() -> Optional[WindowInfo]:
    """通过 X11 EWMH 属性和 xprop 获取活动窗口."""

    if not os.environ.get("DISPLAY"):
        return None
    active_output = _run_command(["xprop", "-root", "_NET_ACTIVE_WINDOW"])
    if not active_output:
        return None
    match = re.search(r"window id #\s*(0x[0-9a-fA-F]+)", active_output)
    if not match or match.group(1) == "0x0":
        return WindowInfo(process_name="unknown", available=False)

    properties = _run_command(
        [
            "xprop",
            "-id",
            match.group(1),
            "_NET_WM_PID",
            "_NET_WM_NAME",
            "WM_NAME",
        ]
    )
    if not properties:
        return None
    pid = _parse_xprop_int(properties, "_NET_WM_PID")
    title = _parse_xprop_string(properties, "_NET_WM_NAME")
    if not title:
        title = _parse_xprop_string(properties, "WM_NAME")
    return _process_window_info(pid, title)


def _parse_xprop_int(output: str, property_name: str) -> int:
    """解析 xprop 返回的整数属性."""

    match = re.search(rf"^{re.escape(property_name)}[^=]*=\s*(\d+)", output, re.MULTILINE)
    return int(match.group(1)) if match else 0


def _parse_xprop_string(output: str, property_name: str) -> str:
    """解析 xprop 返回的带引号字符串属性."""

    match = re.search(rf"^{re.escape(property_name)}[^=]*=\s*(.*)$", output, re.MULTILINE)
    if not match:
        return ""
    value = match.group(1).strip()
    if value.startswith('"'):
        try:
            parsed = ast.literal_eval(value)
            return parsed if isinstance(parsed, str) else ""
        except (SyntaxError, ValueError):
            return value.strip('"')
    return value


def _parse_gdbus_string(output: str) -> Optional[str]:
    """解析 gdbus 对字符串返回值的 tuple 包装."""

    match = re.search(r"'((?:\\.|[^'])*)'", output, re.DOTALL)
    if not match:
        return None
    try:
        value = ast.literal_eval("'" + match.group(1) + "'")
        return value if isinstance(value, str) else None
    except (SyntaxError, ValueError):
        return None


# ── Linux 空闲检测 ──────────────────────────────────────────


def _get_linux_idle_seconds() -> int:
    """获取 Linux 空闲时间，优先使用 GNOME Mutter，再尝试 X11 工具."""

    idle_ms: Optional[int] = None
    if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
        idle_ms = _get_mutter_idle_ms()
    if idle_ms is None:
        idle_ms = _get_x11_idle_ms()
    if idle_ms is None:
        _warn_backend_unavailable(
            "当前 Linux 桌面未提供用户空闲时间接口；将继续记录但不会自动判定空闲",
            idle=True,
        )
        return 0
    return max(0, int(idle_ms / 1000))


def _get_mutter_idle_ms() -> Optional[int]:
    """通过 GNOME Mutter IdleMonitor 获取毫秒级空闲时间."""

    global _MUTTER_IDLE_AVAILABLE
    if _MUTTER_IDLE_AVAILABLE is False:
        return None
    output = _run_command(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.gnome.Mutter.IdleMonitor",
            "--object-path",
            "/org/gnome/Mutter/IdleMonitor/Core",
            "--method",
            "org.gnome.Mutter.IdleMonitor.GetIdletime",
        ]
    )
    if output is None:
        _MUTTER_IDLE_AVAILABLE = False
        return None
    match = re.search(r"uint(?:32|64)\s+(\d+)", output)
    if match is None:
        match = re.search(r"\(\s*(\d+)", output)
    if not match:
        _MUTTER_IDLE_AVAILABLE = False
        return None
    _MUTTER_IDLE_AVAILABLE = True
    return int(match.group(1))


def _get_x11_idle_ms() -> Optional[int]:
    """通过 xprintidle 或 xssstate 获取 X11 空闲时间."""

    if not os.environ.get("DISPLAY"):
        return None
    for command in (("xprintidle",), ("xssstate", "-i")):
        output = _run_command(command)
        if not output:
            continue
        match = re.search(r"(\d+(?:\.\d+)?)", output)
        if match:
            return int(float(match.group(1)))
    return None
