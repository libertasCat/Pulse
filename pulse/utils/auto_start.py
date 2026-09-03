"""开机自启管理 —— Windows 注册表 / Linux XDG Autostart."""

import logging
import os
import shlex
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "Pulse"
_DESKTOP_FILE_NAME = "pulse.desktop"


def _get_pulse_entry_path() -> str:
    """生成 Pulse 启动命令（兼容源码运行和冻结后的可执行文件）."""
    if sys.platform == "win32" and not getattr(sys, "frozen", False):
        # 保持原有 Windows 注册表启动命令格式不变。
        script_dir = Path(__file__).parent.parent.parent
        main_script = script_dir / "main.py"
        return f'"{sys.executable}" "{main_script}"'
    command = _get_pulse_command()
    if sys.platform == "win32":
        import subprocess
        return subprocess.list2cmdline(command)
    return " ".join(shlex.quote(arg) for arg in command)


def _get_pulse_command() -> list[str]:
    """返回启动 Pulse 所需的命令参数."""

    if getattr(sys, "frozen", False):
        return [sys.executable]
    script_dir = Path(__file__).parent.parent.parent
    main_script = script_dir / "main.py"
    if main_script.exists():
        return [sys.executable, str(main_script)]
    # 兼容通过 pip 安装后没有项目根目录 main.py 的情况。
    return [sys.executable, "-m", "pulse.main"]


def _linux_config_dir() -> Path:
    """获取 Linux 用户级 XDG 配置目录."""

    configured = os.environ.get("XDG_CONFIG_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".config"


def _linux_desktop_file() -> Path:
    """获取 Pulse 的 Linux 自启动 desktop 文件路径."""

    return _linux_config_dir() / "autostart" / _DESKTOP_FILE_NAME


def _desktop_exec_arg(value: str) -> str:
    """按 Desktop Entry 规则转义 Exec 参数."""

    if value and all(char not in value for char in ' \t"\\'):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _linux_desktop_entry() -> str:
    """生成 Linux XDG Autostart 文件内容."""

    command = " ".join(_desktop_exec_arg(arg) for arg in _get_pulse_command())
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Pulse\n"
        "Comment=Pulse desktop activity tracker\n"
        f"Exec={command}\n"
        "Terminal=false\n"
        "X-GNOME-Autostart-enabled=true\n"
        "X-KDE-autostart-after=panel\n"
    )


def _set_linux_auto_start(enabled: bool) -> bool:
    """写入或删除 Linux 用户级自启动文件."""

    desktop_file = _linux_desktop_file()
    try:
        if enabled:
            desktop_file.parent.mkdir(parents=True, exist_ok=True)
            temp_file = desktop_file.with_name(f".{desktop_file.name}.tmp")
            temp_file.write_text(_linux_desktop_entry(), encoding="utf-8")
            temp_file.replace(desktop_file)
            logger.info("Linux 登录自启动已启用: %s", desktop_file)
        else:
            desktop_file.unlink(missing_ok=True)
            logger.info("Linux 登录自启动已禁用")
        return True
    except OSError as exc:
        logger.warning("设置 Linux 登录自启动失败: %s", exc)
        return False


def set_auto_start(enabled: bool) -> bool:
    """设置开机自启."""
    if sys.platform.startswith("linux"):
        return _set_linux_auto_start(enabled)
    if sys.platform != "win32":
        logger.warning("当前平台暂不支持开机自启")
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0,
                             winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE)
        if enabled:
            winreg.SetValueEx(key, _REG_NAME, 0, winreg.REG_SZ, _get_pulse_entry_path())
            logger.info("开机自启已启用")
        else:
            try:
                winreg.DeleteValue(key, _REG_NAME)
                logger.info("开机自启已禁用")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except Exception as e:
        logger.warning("设置开机自启失败: %s", e)
        return False


def is_auto_start_enabled() -> bool:
    """检查开机自启是否已启用."""
    if sys.platform.startswith("linux"):
        return _linux_desktop_file().exists()
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY, 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, _REG_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False
