"""Offline integration tests: independent databases, encrypted IMAP and interrupted uploads."""
import os
os.environ.setdefault("PULSE_DATA_DIR", "/private/tmp/pulse-sync-test-default")
import tempfile
import unittest
from datetime import date, datetime
from email import policy
from email.parser import BytesParser
from pathlib import Path
from types import SimpleNamespace

from pulse.db.models import AppSession
from pulse.db.repository import Repository
from pulse.services.sync_store import SyncStore
from pulse.services.mail_sync import MailSync


class FakeMailbox:
    def __init__(self):
        self.messages = []
        self.created = False
        self.fail_after = None

    def client(self, *args, **kwargs):
        return FakeClient(self)


class FakeClient:
    capabilities = ("IMAP4REV1", "ID")

    def __init__(self, mailbox):
        self.mailbox = mailbox

    def login(self, account, password):
        return "OK", []

    def _simple_command(self, *args):
        return "OK", []

    def select(self, folder):
        assert folder == "PulseSync"
        return ("OK" if self.mailbox.created else "NO"), []

    def create(self, folder):
        self.mailbox.created = True
        return "OK", []

    def logout(self):
        return "BYE", []

    def uid(self, command, *args):
        if command == "search":
            return "OK", [b" ".join(str(i + 1).encode() for i in range(len(self.mailbox.messages)))]
        assert command == "fetch"
        uid, query = args
        raw = self.mailbox.messages[int(uid) - 1]
        metadata = f"1 (RFC822.SIZE {len(raw)})".encode()
        if query == "(RFC822.SIZE)":
            return "OK", [metadata]
        if "HEADER" in query:
            raw = raw.split(b"\r\n\r\n")[0] + b"\r\n\r\n"
        assert "PEEK" in query
        return "OK", [(metadata, raw), b")"]

    def append(self, folder, flags, timestamp, raw):
        if self.mailbox.fail_after == len(self.mailbox.messages):
            return "NO", []
        self.mailbox.messages.append(raw)
        return "OK", []


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repos = []
        self.stores = []
        for name in ("mac", "windows"):
            folder = Path(self.temp.name) / name
            folder.mkdir()
            repo = Repository(str(folder / "pulse.db"))
            repo.initialize_db()
            self.repos.append(repo)
            self.stores.append(SyncStore(repo))
        self.mailbox = FakeMailbox()
        self.cfg = SimpleNamespace(account="test@163.com")

    def tearDown(self):
        for repo in self.repos:
            repo._engine.dispose()
        self.temp.cleanup()

    def sync(self, index, mode="sync"):
        return MailSync(self.stores[index], self.cfg, "test-authorization",
                        "shared-secret", self.mailbox.client).run(mode)

    def task_titles(self, index):
        with self.stores[index].connect() as db:
            return [r[0] for r in db.execute("SELECT title FROM calendar_tasks ORDER BY title")]

    def test_independent_ids_bidirectional_merge_and_no_duplicate_upload(self):
        for i, name in enumerate(("Mac task", "Windows task")):
            self.repos[i].create_task(date.today(), name)
        self.sync(0)
        self.sync(1)
        self.sync(0)
        self.assertEqual(self.task_titles(0), ["Mac task", "Windows task"])
        self.assertEqual(self.task_titles(1), self.task_titles(0))
        count = len(self.mailbox.messages)
        self.sync(0)
        self.sync(1)
        self.assertEqual(len(self.mailbox.messages), count)

    def test_deletion_propagates_without_resurrection(self):
        task = self.repos[0].create_task(date.today(), "delete me")
        self.sync(0)
        self.sync(1)
        self.repos[0].delete_task(task.id)
        self.sync(0)
        self.sync(1)
        self.assertEqual(self.task_titles(1), [])
        self.sync(0)
        self.assertEqual(self.task_titles(0), [])

    def test_pull_does_not_upload_or_discard_local_data(self):
        self.repos[0].create_task(date.today(), "remote")
        self.repos[1].create_task(date.today(), "local")
        self.sync(0)
        count = len(self.mailbox.messages)
        self.sync(1, "pull")
        self.assertEqual(len(self.mailbox.messages), count)
        self.assertEqual(self.task_titles(1), ["local", "remote"])

    def test_overwrite_tombstones_cloud_only_records(self):
        self.repos[0].create_task(date.today(), "cloud only")
        self.sync(0)
        self.repos[1].create_task(date.today(), "authoritative local")
        self.sync(1, "overwrite")
        self.sync(0, "pull")
        self.assertEqual(self.task_titles(0), ["authoritative local"])
        self.assertEqual(self.task_titles(1), ["authoritative local"])
        self.assertTrue(list((self.stores[1].path.parent / "sync-backups").glob("*.db")))

    def test_edit_conflict_is_deterministic_and_recoverable(self):
        task = self.repos[0].create_task(date.today(), "original")
        self.sync(0)
        self.sync(1)
        for i, title in enumerate(("Mac edit", "Windows edit")):
            with self.stores[i].connect() as db:
                db.execute("UPDATE calendar_tasks SET title=?", (title,))
        self.sync(0)
        self.sync(1)
        self.sync(0)
        self.assertEqual(self.task_titles(0), self.task_titles(1))
        total = 0
        for store in self.stores:
            with store.connect() as db:
                total += db.execute("SELECT COUNT(*) FROM pulse_sync_conflicts").fetchone()[0]
        self.assertGreater(total, 0)

    def test_attachments_and_sessions_round_trip(self):
        task = self.repos[0].create_task(date.today(), "image")
        field = self.repos[0].add_task_field(task.id, "text")
        self.stores[0].attachments.mkdir(parents=True)
        (self.stores[0].attachments / "test.png").write_bytes(b"test image bytes")
        with self.stores[0].connect() as db:
            db.execute("UPDATE calendar_task_fields SET kind='image',image_path='test.png' WHERE id=?", (field.id,))
        self.repos[0].save_session(AppSession(process_name="Safari", window_title="Private title",
                                             start_time=datetime.now(), duration_seconds=20))
        self.sync(0)
        self.sync(1)
        with self.stores[1].connect() as db:
            row = db.execute("SELECT image_path FROM calendar_task_fields").fetchone()
            self.assertEqual(self.stores[1]._image_path(row[0]).read_bytes(), b"test image bytes")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM app_sessions").fetchone()[0], 1)
        self.assertNotIn(b"Private title", b"".join(self.mailbox.messages))

    def test_wrong_password_fails_without_local_change(self):
        self.repos[0].create_task(date.today(), "secret")
        self.sync(0)
        sync = MailSync(self.stores[1], self.cfg, "test-authorization", "wrong", self.mailbox.client)
        with self.assertRaisesRegex(ValueError, "解密"):
            sync.run()
        self.assertEqual(self.task_titles(1), [])

    def test_mapping_comments_and_checklists_keep_foreign_keys(self):
        for repo in self.repos:
            category = repo.get_all_categories()[0]
            repo.save_app_category("Safari", category.id)
        task = self.repos[0].create_task(date.today(), "nested")
        self.repos[0].add_comment(task.id, "comment")
        checklist = self.repos[0].add_checklist(task.id, "list")
        item = self.repos[0].add_checklist_item(checklist.id, "item")
        self.repos[0].set_checklist_item_done(item.id, True)
        self.sync(0)
        self.sync(1)
        self.sync(0)
        with self.stores[1].connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM app_categories").fetchone()[0], 1)
            row = db.execute(
                "SELECT i.content,i.done,t.title FROM checklist_items i "
                "JOIN checklists c ON c.id=i.checklist_id JOIN calendar_tasks t ON t.id=c.task_id"
            ).fetchone()
            self.assertEqual(tuple(row), ("item", 1, "nested"))
            self.assertEqual(db.execute("SELECT content FROM calendar_comments").fetchone()[0], "comment")

    def test_multichunk_payload_and_interrupted_upload(self):
        from unittest.mock import patch
        self.repos[0].create_task(date.today(), "chunks")
        # Small chunks exercise actual message boundaries without huge fixtures.
        with patch("pulse.services.mail_sync.CHUNK", 512):
            self.sync(0)
            self.assertGreater(len(self.mailbox.messages), 1)
            self.sync(1, "pull")
            self.assertEqual(self.task_titles(1), ["chunks"])
            before = len(self.mailbox.messages)
            self.repos[0].create_task(date.today(), "incomplete")
            self.mailbox.fail_after = before + 1
            with self.assertRaisesRegex(ValueError, "上传"):
                self.sync(0)
            self.mailbox.fail_after = None
            self.sync(1, "pull")
            self.assertEqual(self.task_titles(1), ["chunks"])

    def test_incomplete_upload_keeps_previous_snapshot(self):
        self.repos[0].create_task(date.today(), "complete")
        self.sync(0)
        message = BytesParser(policy=policy.default).parsebytes(self.mailbox.messages[-1])
        import uuid
        message.replace_header("X-Pulse-Bundle", str(uuid.uuid4()))
        message.replace_header("X-Pulse-Parts", "2")
        self.mailbox.messages.append(message.as_bytes(policy=policy.SMTP))
        self.sync(1, "pull")
        self.assertEqual(self.task_titles(1), ["complete"])

    def test_transaction_rolls_back_broken_relationship(self):
        snapshot = self.stores[0].snapshot()
        task = self.repos[0].create_task(date.today(), "broken")
        self.repos[0].add_task_field(task.id, "field")
        snapshot = self.stores[0].snapshot()
        for item in snapshot["records"].values():
            if item["tab"] == "calendar_task_fields":
                item["data"]["task_id"] = "missing-id"
        with self.assertRaises(ValueError):
            self.stores[1].merge(snapshot)
        self.assertEqual(self.task_titles(1), [])
        with self.stores[1].connect() as db:
            self.assertEqual(db.execute("SELECT importing FROM pulse_sync_meta").fetchone()[0], 0)

    def test_database_restore_keeps_ids_but_uses_new_device(self):
        source = self.stores[0]
        with source.connect() as db, self.stores[1].connect() as target:
            db.backup(target)
        restored = SyncStore(self.repos[1])
        self.assertNotEqual(restored.device, source.device)
        self.assertEqual(set(restored.snapshot()["records"]), set(source.snapshot()["records"]))

    def test_parent_delete_dominates_newer_offline_child_edit(self):
        task = self.repos[0].create_task(date.today(), "parent")
        field = self.repos[0].add_task_field(task.id, "child")
        self.sync(0)
        self.sync(1)
        self.repos[0].delete_task(task.id)
        with self.stores[1].connect() as db:
            db.execute("UPDATE pulse_sync_meta SET clock=1000")
            db.execute("UPDATE calendar_task_fields SET content='newer offline edit'")
        self.sync(1)
        self.sync(0)
        self.sync(1)
        self.assertEqual(self.task_titles(1), [])
        for store in self.stores:
            with store.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM calendar_task_fields").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
