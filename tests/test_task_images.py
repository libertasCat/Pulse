"""Task image persistence, ordering, clipboard and legacy migration regression."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import tempfile
from pathlib import Path
from datetime import date
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QColor
from PyQt6.QtCore import QMimeData
from sqlalchemy import text
from pulse.db.repository import Repository
from pulse.ui.widgets.task_detail_dialog import TaskDetailDialog


def run():
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as directory:
        repo = Repository(str(Path(directory) / 'pulse.db'))
        repo.initialize_db()
        task = repo.create_task(date.today(), 'Images')
        first = repo.add_task_field(task.id, 'before')
        repo.add_task_field(task.id, 'after')
        image = QImage(120, 240, QImage.Format.Format_ARGB32)
        image.fill(QColor('red'))
        field = repo.add_task_image(task.id, image, first.id)
        path = repo.image_file(field.image_path)
        assert path.exists()
        assert [f.kind for f in repo.get_task_by_id(task.id).fields] == ['text', 'image', 'text']
        dialog = TaskDetailDialog(task.id, repo)
        dialog.show()
        app.processEvents()
        mime = QMimeData()
        mime.setImageData(image)
        dialog._field_edits[0].insertFromMimeData(mime)
        app.processEvents()
        assert len(repo.get_task_by_id(task.id).fields) == 4
        dialog.close()
        reopened = TaskDetailDialog(task.id, repo)
        assert reopened._fields_layout.count() == 4
        reopened.close()
        repo.delete_task_field(field.id)
        assert not path.exists()
        remaining = [repo.image_file(f.image_path) for f in repo.get_task_by_id(task.id).fields if f.kind == 'image']
        repo.delete_task(task.id)
        assert all(not p.exists() for p in remaining)
        # Recreate the pre-image schema, then run the migration twice.
        with repo.session() as session:
            session.execute(text('DROP TABLE calendar_task_fields'))
            session.execute(text('CREATE TABLE calendar_task_fields (id INTEGER PRIMARY KEY, task_id INTEGER, content TEXT, sort_order INTEGER, created_at DATETIME)'))
            session.execute(text("INSERT INTO calendar_task_fields (id,task_id,content,sort_order) VALUES (1,1,'legacy',1)"))
        repo.initialize_db()
        repo.initialize_db()
        with repo.session() as session:
            assert session.execute(text('SELECT kind,content FROM calendar_task_fields')).one() == ('text', 'legacy')
        repo._engine.dispose()
    print('task images regression passed')

if __name__ == '__main__':
    run()
