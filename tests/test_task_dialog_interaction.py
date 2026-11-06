"""Backdrop dismissal and fixed header on a long task."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from datetime import date
from pathlib import Path
import tempfile
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton
from pulse.db.repository import Repository
from pulse.ui.theme import ThemeManager, ThemeMode
from pulse.ui.widgets.task_detail_dialog import TaskDetailDialog


def run():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as directory:
        repo = Repository(str(Path(directory) / 'test.db'))
        repo.initialize_db()
        task = repo.create_task(date.today(), 'Long task')
        repo.add_task_field(task.id, '\n'.join(['Long content'] * 80))
        for mode in (ThemeMode.LIGHT, ThemeMode.DARK):
            ThemeManager.instance().set_mode(mode)
            ThemeManager.instance().apply()
            dialog = TaskDetailDialog(task.id, repo)
            dialog.show()
            app.processEvents()
            QTest.qWait(30)
            close = dialog.findChild(QPushButton, 'taskClose')
            before = close.mapTo(dialog, QPoint())
            dialog._content_scroll.verticalScrollBar().setValue(
                dialog._content_scroll.verticalScrollBar().maximum())
            app.processEvents()
            assert close.mapTo(dialog, QPoint()) == before
            QTest.mouseClick(dialog._card, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
            assert dialog.isVisible()
            dialog._title_edit.setText('Saved by outside click')
            QTest.mouseClick(dialog, Qt.MouseButton.LeftButton, pos=QPoint(5, 5))
            assert not dialog.isVisible()
            assert repo.get_task_by_id(task.id).title == 'Saved by outside click'
            dialog = TaskDetailDialog(task.id, repo)
            dialog.show()
            app.processEvents()
            dialog.grab().save(str(Path('build') / ('task-dialog-' + mode.value + '.png')))
            dialog._content_scroll.verticalScrollBar().setValue(
                dialog._content_scroll.verticalScrollBar().maximum())
            app.processEvents()
            QTest.qWait(50)
            dialog._content_scroll.verticalScrollBar().setValue(
                dialog._content_scroll.verticalScrollBar().maximum())
            app.processEvents()
            dialog.grab().save(str(Path('build') / ('task-dialog-' + mode.value + '-bottom.png')))
            edit = dialog._field_edits[0]
            assert edit.height() >= edit.document().size().height()
            assert edit.parentWidget().height() >= edit.height()
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
            assert not dialog.isVisible()
        repo._engine.dispose()
    print('task dialog interaction passed')

if __name__ == '__main__':
    run()
