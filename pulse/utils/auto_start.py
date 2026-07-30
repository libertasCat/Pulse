"""开机自启管理 —— Windows 注册表."""

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_REG_NAME = "Pulse"


def _get_pulse_entry_path() -> str:
    """生成 Pulse 启动命令（使用当前 Python 解释器）. """
    python_path = sys.executable
    script_dir = Path(__file__).parent.parent.parent
    main_script = script_dir / "main.py"
    return f'"{python_path}" "{main_script}"'


def set_auto_start(enabled: bool) -> bool:
    """设置开机自启."""
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
