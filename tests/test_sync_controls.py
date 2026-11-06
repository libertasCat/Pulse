"""Offline UI regression: no personal credentials or IMAP connections."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication, QMessageBox
from pulse.ui.sync_controls import SyncControls
from pulse.ui.theme import ThemeManager, ThemeMode
from pulse.utils.config import ConfigManager
from pulse.db.repository import Repository


class SyncControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_buttons_validation_busy_and_cancel(self):
        with tempfile.TemporaryDirectory() as directory:
            config = ConfigManager(Path(directory) / 'config.json')
            repo = Repository(str(Path(directory) / 'pulse.db'))
            repo.initialize_db()
            with patch('pulse.ui.sync_controls.load_secrets', return_value={}):
                controls = SyncControls(config, repo)
            controls.account.setText('invalid')
            self.assertFalse(controls.save())
            controls.account.setText('test@163.com')
            controls.auth.setText('test-only')
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No), patch('pulse.ui.sync_controls.threading.Thread') as worker:
                controls.buttons[2].click()
                worker.assert_not_called()
                self.assertFalse(controls.busy)
            with patch('pulse.ui.sync_controls.threading.Thread') as worker:
                controls.buttons[0].click()
                self.assertTrue(controls.busy)
                self.assertTrue(all(not widget.isEnabled() for widget in controls.inputs + controls.buttons))
                controls.start()
                self.assertEqual(worker.call_count, 1)
            controls._finished(False, '测试失败反馈')
            self.assertTrue(all(widget.isEnabled() for widget in controls.inputs + controls.buttons))
            controls.resize(760, 340)
            controls.show()
            for mode in (ThemeMode.LIGHT, ThemeMode.DARK):
                ThemeManager.instance().set_mode(mode)
                self.app.processEvents()
                Path('build').mkdir(exist_ok=True)
                self.assertTrue(controls.grab().save(f'build/sync-controls-{mode.value}.png'))
            controls._shutdown()
            controls.close()
            repo._engine.dispose()


if __name__ == '__main__':
    unittest.main()
