"""进程名处理 —— 去后缀、美化."""

import re

_EXE_EXTENSIONS = re.compile(r"\.(exe|py|jar|app|bin|sh|bat|cmd)$", re.IGNORECASE)


def strip_ext(process_name: str) -> str:
    """去除可执行文件后缀，如 'chrome.exe' → 'chrome'."""
    return _EXE_EXTENSIONS.sub("", process_name)


def format_process_name(process_name: str) -> str:
    """美化进程名：去后缀 + 首字母大写."""
    name = strip_ext(process_name)
    # 将下划线/连字符替换为空格
    name = name.replace("_", " ").replace("-", " ")
    # 首字母大写
    return name.strip()
