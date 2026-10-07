"""Packaged-runtime check without user data, tracking or network requests."""

def run():
    import json
    import sys
    import traceback
    from pathlib import Path
    output = Path(sys.argv[sys.argv.index('--self-test') + 1])
    result = {'ok': False}
    try:
        import ssl
        import psutil
        import win32api
        from openai import OpenAI
        from sqlalchemy import create_engine, text
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
        from pulse.ui.widgets.notion_grid import NotionGrid
        from pulse import __version__
        from datetime import date
        from types import SimpleNamespace
        ssl.create_default_context()
        with OpenAI(api_key='self-test', base_url='https://api.deepseek.com'):
            pass
        engine = create_engine('sqlite:///:memory:')
        with engine.connect() as connection:
            assert connection.execute(text('select 1')).scalar() == 1
        engine.dispose()
        app = QApplication([])
        grid = NotionGrid()
        grid.set_data(2026, 9, [(SimpleNamespace(id=1, date=date(2026, 9, 1),
                      end_date=date(2026, 9, 30), title='Release test'),)])
        grid.resize(900, 650)
        grid.show()
        QTimer.singleShot(300, app.quit)
        app.exec()
        assert not grid.grab().isNull()
        import tempfile
        from PyQt6.QtGui import QImage, QColor
        from PyQt6.QtCore import QMimeData
        from pulse.db.repository import Repository
        from pulse.ui.widgets.task_detail_dialog import TaskDetailDialog
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(str(Path(directory) / 'pulse.db'))
            repo.initialize_db()
            task = repo.create_task(date.today(), 'Image release check')
            repo.add_task_field(task.id, 'Paste here')
            dialog = TaskDetailDialog(task.id, repo)
            image = QImage(120, 240, QImage.Format.Format_ARGB32)
            image.fill(QColor('red'))
            mime = QMimeData()
            mime.setImageData(image)
            dialog._field_edits[0].insertFromMimeData(mime)
            assert len(repo.get_task_by_id(task.id).fields) == 2
            dialog.close()
            reopened = TaskDetailDialog(task.id, repo)
            reopened.show()
            app.processEvents()
            assert not reopened.grab().isNull()
            assert reopened._fields_layout.count() == 2
            reopened.close()
            repo.delete_task(task.id)
            assert not list(repo._attachment_root.glob('*.png'))
            repo._engine.dispose()
        result = {'ok': True, 'version': __version__, 'ssl': ssl.OPENSSL_VERSION,
                  'qt_platform': app.platformName(), 'task_images': 'passed'}
    except BaseException:
        result['error'] = traceback.format_exc()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    sys.exit(0 if result['ok'] else 1)
