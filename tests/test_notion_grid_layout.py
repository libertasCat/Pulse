"""Notion 月历跨周任务布局回归测试。"""

from datetime import date

from PyQt6.QtWidgets import QApplication

from pulse.ui.widgets.notion_grid import NotionGrid


def test_cross_week_task_reflows_in_each_calendar_row():
    """跨周任务应按自然周重新压紧，不能把首周高槽位带到月底。"""
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

    task_rows = grid._get_stack()
    assert task_rows[(3, 0)] == 2
    assert task_rows[(3, 1)] == 2
    assert task_rows[(3, 2)] == 0
    assert task_rows[(3, 3)] == 0
    assert task_rows[(3, 4)] == 0

    heights = grid._natural_heights()
    crowded_height = 34 + 3 * 22 + 4
    compact_height = 34 + 1 * 22 + 4
    assert heights[0] >= crowded_height
    assert heights[1] >= crowded_height
    assert heights[2] == compact_height
    assert heights[3] == compact_height
    assert heights[4] == compact_height

    grid.deleteLater()
    del app
