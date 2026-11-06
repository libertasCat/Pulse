"""Statistics query counts, aggregation boundaries, async navigation and calendar previews."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from sqlalchemy import event, text
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from PyQt6.QtCore import QPoint, Qt
from pulse.db.repository import Repository
from pulse.db.models import AppSession, CalendarTask
from pulse.ui.pages.stats_page import StatsPage
from pulse.ui.pages.calendar_page import CalendarPage
from pulse.ui.theme import ThemeManager, ThemeMode
from pulse.ui.widgets.notion_grid import NotionGrid
from pulse.utils.config import ConfigManager


class StatisticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Repository(str(Path(self.temp.name) / 'pulse.db'))
        self.repo.initialize_db()

    def tearDown(self):
        self.repo._engine.dispose()
        self.temp.cleanup()

    def test_batch_month_and_index(self):
        rows = [dict(process_name='test.exe', start_time=datetime(2026, 1, 1) + timedelta(minutes=i * 10),
                     duration_seconds=30, is_idle=False) for i in range(20000)]
        rows += [dict(process_name='idle', start_time=datetime(2026, 2, 1), duration_seconds=999, is_idle=True)]
        with self.repo._engine.begin() as connection:
            connection.execute(AppSession.__table__.insert(), rows)
        statements = []
        def record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(self.repo._engine, 'before_cursor_execute', record)
        started = time.perf_counter()
        days = self.repo.get_daily_totals_for_month(2026, 2)
        elapsed = time.perf_counter() - started
        self.assertEqual(len(statements), 1)
        self.assertEqual(len(days), 28)
        self.assertEqual(days[0]['total_seconds'], 144 * 30)
        self.assertEqual(days[-1]['date'], date(2026, 2, 28))
        statements.clear()
        legacy_started = time.perf_counter()
        legacy = [self.repo.get_total_duration_by_date(date(2026, 2, 1) + timedelta(days=i)) for i in range(28)]
        legacy_elapsed = time.perf_counter() - legacy_started
        self.assertEqual(len(statements), 28)
        self.assertEqual([day['total_seconds'] for day in days], legacy)
        self.assertEqual(self.repo.get_daily_summaries(date(2027, 1, 1), 2)[0]['total_seconds'], 0)
        self.assertEqual(self.repo.get_daily_summaries(date.today(), 0), [])
        self.repo._migrate()  # Migration is repeatable on old and new databases.
        with self.repo._engine.connect() as connection:
            plan = connection.execute(text("EXPLAIN QUERY PLAN SELECT SUM(duration_seconds) FROM app_sessions WHERE start_time >= '2026-02-01' AND start_time < '2026-03-01'")).all()
        self.assertIn('ix_app_sessions_start_time', str(plan))
        print(f'20,000 sessions: month aggregation {elapsed * 1000:.1f}ms / 1 SQL; daily loop {legacy_elapsed * 1000:.1f}ms / 28 SQL (both indexed)')

    def test_async_navigation_and_calendar_render(self):
        page = StatsPage(self.repo)
        page._tab_group.button(2).click()
        page._month_offset = -1
        page._refresh()
        deadline = time.monotonic() + 8
        while page._jobs and time.monotonic() < deadline:
            QTest.qWait(20)
        self.assertFalse(page._jobs)
        self.assertIn('年', page._month_label.text())
        month_index = date.today().year * 12 + date.today().month - 2
        year, month = divmod(month_index, 12)
        self.assertEqual(page._month_label.text(), f'{year}年{month + 1}月')
        page.close()
        task = self.repo.create_task(date(2026, 11, 3), '跨周项目 · 设计与开发')
        with self.repo.session() as session:
            session.query(CalendarTask).filter_by(id=task.id).update({'end_date': date(2026, 11, 18)})
        self.repo.create_task(date(2026, 11, 6), '整理实验记录与图片')
        calendar = CalendarPage(self.repo)
        calendar._view_year, calendar._view_month = 2026, 11
        calendar._refresh_grid()
        calendar.resize(1000, 760)
        calendar.show()
        Path('build').mkdir(exist_ok=True)
        for mode in (ThemeMode.LIGHT, ThemeMode.DARK):
            ThemeManager.instance().set_mode(mode)
            self.app.processEvents()
            self.assertTrue(calendar.grab().save(f'build/calendar-notion-{mode.value}.png'))
        calendar._on_cell_add(2026, 11, 6)
        self.assertEqual(calendar._popup._title_input.text(), '')
        calendar._popup.close()
        calendar.close()

    def test_cross_week_edges_and_crowded_cells(self):
        grid = NotionGrid()
        grid._year, grid._month, grid._first_wd, grid._last_day = 2026, 9, 1, 30
        grid._tasks = [(1, date(2026, 9, 1), date(2026, 9, 20), '跨周任务')]
        grid.resize(900, 700)
        grid.show()
        self.app.processEvents()
        selected = []
        grid.on_task_click = selected.append
        y = int(grid._row_y(1) + 42)
        QTest.mouseClick(grid, Qt.MouseButton.LeftButton, pos=QPoint(grid.width() - 3, y))
        QTest.mouseClick(grid, Qt.MouseButton.LeftButton, pos=QPoint(int(grid._cell_w + 3), y))
        self.assertEqual(selected, [1, 1])
        self.assertIsNone(grid._drag_left_task_id)
        self.assertIsNone(grid._drag_side_task_id)
        grid._tasks = [(i, date(2026, 9, 1), date(2026, 9, 1), str(i)) for i in range(25)]
        slots = grid._get_stack()
        self.assertEqual(len(set(slots.values())), 25)
        grid.close()


if __name__ == '__main__':
    unittest.main()
