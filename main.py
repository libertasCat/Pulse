"""Pulse —— 直接运行即启动桌面 GUI."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

if __name__ == "__main__":
    from pulse.main import run_gui
    run_gui()
