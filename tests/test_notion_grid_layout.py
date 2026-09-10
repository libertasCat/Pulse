"""Notion 月历跨周任务布局回归测试。"""

from datetime import date

from PyQt6.QtWidgets import QApplication

from pulse.ui.widgets.notion_grid import NotionGrid


def test_cross_week_task_reserves_stack_height_in_every_row():
    """跨周任务在后续周仍处于高槽位时，不得越过下一行日期头。"""
    app = QApplication.instance() or QApplication([])
    grid = NotionGrid()
    grid._year = 2026
    grid._month = 9
    grid._first_wd = date(2026, 9, 1).weekday()
    grid._last_day = 30
    grid._tasks = [
        (1, date(2026, 9, 1), date(2026, 9, 10), "占位任务 1"),
        (2, date(2026, 9, 2), date(2026, 9, 11), "占位任务 2"),
        (3, date(2026, 9, 3), date(2026, 9, 30), "github学习LLM，agent"),
    ]

    stack_row = grid._get_stack()[3]
    assert stack_row == 2

    heights = grid._natural_heights()
    required_height = 34 + (stack_row + 1) * 22 + 4
    for calendar_row in range(5):
        assert heights[calendar_row] >= required_height

    grid.deleteLater()
    del app
