"""Record-level offline sync, stable identities, tombstones and Lamport clocks."""
import base64
import copy
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from pulse.db.models import Base

TABLES = [t.name for t in Base.metadata.sorted_tables]
RELATIONS = {
    t.name: {fk.parent.name: fk.column.table.name for fk in t.foreign_keys}
    for t in Base.metadata.sorted_tables
}
MAX_BYTES = 20 * 1024 * 1024


class SyncStore:
    def __init__(self, repo):
        self.path = Path(repo._engine.url.database)
        self.attachments = repo._attachment_root
        # Identity stays outside the DB so database restores on another device
        # cannot make two installations overwrite the same mail stream.
        identity_path = self.path.parent / "sync-device-id"
        try:
            fd = os.open(str(identity_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "w") as stream:
                stream.write(uuid.uuid4().hex)
        self.device = uuid.UUID(identity_path.read_text().strip()).hex
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS pulse_sync_meta (
                    id INTEGER PRIMARY KEY CHECK(id=1), device TEXT, clock INTEGER, importing INTEGER);
                CREATE TABLE IF NOT EXISTS pulse_sync_records (
                    sid TEXT PRIMARY KEY, tab TEXT, local_id INTEGER,
                    version INTEGER, origin TEXT, deleted INTEGER DEFAULT 0);
                CREATE UNIQUE INDEX IF NOT EXISTS pulse_sync_live
                    ON pulse_sync_records(tab,local_id) WHERE deleted=0;
                CREATE TABLE IF NOT EXISTS pulse_sync_conflicts (
                    id INTEGER PRIMARY KEY, sid TEXT, saved_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    local_data TEXT, remote_data TEXT);
            """)
            db.execute("INSERT OR IGNORE INTO pulse_sync_meta VALUES(1,?,0,0)", (self.device,))
            db.execute("UPDATE pulse_sync_meta SET device=? WHERE id=1", (self.device,))
            for table in TABLES:
                unindexed = db.execute(
                    f'SELECT t.* FROM "{table}" t LEFT JOIN pulse_sync_records r '
                    "ON r.tab=? AND r.local_id=t.id AND r.deleted=0 WHERE r.sid IS NULL",
                    (table,),
                ).fetchall()
                for row in unindexed:
                    # Built-in categories and process mappings mean the same thing on each device.
                    natural = row["name"] if table == "categories" else (
                        row["process_name"] if table == "app_categories" else None
                    )
                    sid = f"{table}:{natural}" if natural else uuid.uuid4().hex
                    db.execute("UPDATE pulse_sync_meta SET clock=clock+1")
                    clock = db.execute("SELECT clock FROM pulse_sync_meta").fetchone()[0]
                    db.execute("INSERT INTO pulse_sync_records VALUES(?,?,?,?,?,0)",
                               (sid, table, row["id"], clock, self.device))
                for action in ("INSERT", "UPDATE", "DELETE"):
                    prefix = "OLD" if action == "DELETE" else "NEW"
                    if action == "INSERT":
                        identity = (f"'{table}:' || NEW.name" if table == "categories" else
                                    f"'{table}:' || NEW.process_name" if table == "app_categories" else
                                    "lower(hex(randomblob(16)))")
                        change = f"""
                            INSERT OR REPLACE INTO pulse_sync_records
                            SELECT {identity},'{table}',NEW.id,clock,device,0 FROM pulse_sync_meta;
                        """
                    else:
                        change = f"""
                            UPDATE pulse_sync_records SET
                              version=(SELECT clock FROM pulse_sync_meta),
                              origin=(SELECT device FROM pulse_sync_meta),
                              deleted={1 if action == 'DELETE' else 0}
                            WHERE tab='{table}' AND local_id={prefix}.id AND deleted=0;
                        """
                    db.executescript(f"""
                        CREATE TRIGGER IF NOT EXISTS pulse_sync_{table}_{action}
                        AFTER {action} ON "{table}" WHEN (SELECT importing FROM pulse_sync_meta)=0
                        BEGIN
                          UPDATE pulse_sync_meta SET clock=clock+1;
                          {change}
                        END;
                    """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(str(self.path), timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def snapshot(self, db=None):
        if db is None:
            with self.connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                return self.snapshot(connection)
        records = db.execute("SELECT * FROM pulse_sync_records").fetchall()
        identities = {(r["tab"], r["local_id"]): r["sid"] for r in records if not r["deleted"]}
        result = {}
        blobs = {}
        for record in records:
            item = dict(record)
            item.pop("local_id")
            item["data"] = None
            if not record["deleted"]:
                row = db.execute(f'SELECT * FROM "{record["tab"]}" WHERE id=?', (record["local_id"],)).fetchone()
                if row is None:
                    raise ValueError("同步索引不完整")
                data = dict(row)
                data.pop("id")
                for field, parent in RELATIONS[record["tab"]].items():
                    data[field] = identities.get((parent, data[field])) if data[field] is not None else None
                if record["tab"] == "calendar_task_fields" and data.get("image_path"):
                    path = self._image_path(data["image_path"])
                    if not path.is_file():
                        raise ValueError("图片附件缺失，请恢复附件后再同步")
                    if path.stat().st_size > MAX_BYTES:
                        raise ValueError("图片附件超过 20 MB，请减少图片后重试")
                    raw = path.read_bytes()
                    digest = hashlib.sha256(raw).hexdigest()
                    blobs[digest] = base64.b64encode(raw).decode()
                    if sum(len(value) for value in blobs.values()) > MAX_BYTES:
                        raise ValueError("同步附件超过 20 MB，请减少图片后重试")
                    data["image_path"] = digest
                item["data"] = data
            result[item["sid"]] = item
        return {"schema": 1, "device": self.device, "records": result, "blobs": blobs}

    def _image_path(self, name):
        path = (self.attachments / name).resolve()
        if path.parent != self.attachments.resolve():
            raise ValueError("无效附件路径")
        return path

    @staticmethod
    def rank(item):
        return (item["version"], item["origin"])

    @staticmethod
    def validate(snapshot):
        if snapshot.get("schema") != 1 or not isinstance(snapshot.get("records"), dict):
            raise ValueError("不支持的同步数据格式")
        for sid, item in snapshot["records"].items():
            if item.get("sid") != sid or item.get("tab") not in TABLES:
                raise ValueError("无效同步记录")
            if not isinstance(item.get("version"), int) or item["version"] < 0:
                raise ValueError("无效同步版本")
            if not isinstance(item.get("origin"), str) or item.get("deleted") not in (0, 1):
                raise ValueError("无效同步记录")
            if not item["deleted"]:
                columns = {c.name for c in Base.metadata.tables[item["tab"]].columns} - {"id"}
                if not isinstance(item.get("data"), dict) or set(item["data"]) != columns:
                    raise ValueError("同步字段不匹配")
        for digest, encoded in snapshot.get("blobs", {}).items():
            if hashlib.sha256(base64.b64decode(encoded, validate=True)).hexdigest() != digest:
                raise ValueError("图片校验失败")

    def backup(self):
        from datetime import datetime
        folder = self.path.parent / "sync-backups"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".db")
        with self.connect() as source, sqlite3.connect(str(path)) as destination:
            source.backup(destination)
        path.chmod(0o600)
        return path

    def _resolve_deleted_parents(self, local, remote):
        """Deleting a task dominates concurrent edits to its dependent blocks."""
        records = copy.deepcopy(local["records"])
        for sid, item in remote.items():
            if sid not in records or self.rank(item) > self.rank(records[sid]):
                records[sid] = copy.deepcopy(item)
        changed = True
        while changed:
            changed = False
            for item in records.values():
                if item["deleted"]:
                    continue
                for field, parent_table in RELATIONS[item["tab"]].items():
                    sid = item["data"][field]
                    if sid is None:
                        continue
                    parent = records.get(sid)
                    if parent is None or parent["tab"] != parent_table:
                        raise ValueError("同步数据缺少关联记录")
                    if not parent["deleted"]:
                        continue
                    item["version"] = max(item["version"], parent["version"]) + 1
                    item["origin"] = "relation"
                    if Base.metadata.tables[item["tab"]].columns[field].nullable:
                        item["data"][field] = None
                    else:
                        item["deleted"], item["data"] = 1, None
                    changed = True
                    if item["deleted"]:
                        break
        return records

    def merge(self, incoming, overwrite=False):
        """Import only winning records in one transaction; retain losing edits for recovery."""
        self.validate(incoming)
        if not overwrite:
            with self.connect() as db:
                versions = {r["sid"]: (r["version"], r["origin"]) for r in
                            db.execute("SELECT sid,version,origin FROM pulse_sync_records")}
            if not any(sid not in versions or self.rank(item) > versions[sid]
                       for sid, item in incoming["records"].items()):
                return 0
        self.backup()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            local = self.snapshot(db)
            remote = incoming["records"]
            if overwrite:
                # Explicit upload overwrite: dominate remote versions, tombstone cloud-only rows.
                clock = max([i["version"] for i in list(local["records"].values()) + list(remote.values())] + [0]) + 1
                for sid, item in remote.items():
                    if sid not in local["records"]:
                        db.execute("INSERT INTO pulse_sync_records VALUES(?,?,NULL,?,?,1)",
                                   (sid, item["tab"], clock, self.device))
                db.execute("UPDATE pulse_sync_records SET version=?,origin=?", (clock, self.device))
                db.execute("UPDATE pulse_sync_meta SET clock=?", (clock,))
                return 0
            remote = self._resolve_deleted_parents(local, remote)
            winners = [item for sid, item in remote.items()
                       if sid not in local["records"] or self.rank(item) > self.rank(local["records"][sid])]
            db.execute("UPDATE pulse_sync_meta SET importing=1")
            max_clock = max([i["version"] for i in remote.values()] + [0])
            db.execute("UPDATE pulse_sync_meta SET clock=MAX(clock,?)", (max_clock,))
            # Keep a durable copy before concurrent edits are replaced.
            for item in winners:
                old = local["records"].get(item["sid"])
                if old and old["data"] != item["data"]:
                    db.execute("INSERT INTO pulse_sync_conflicts(sid,local_data,remote_data) VALUES(?,?,?)",
                               (item["sid"], json.dumps(old), json.dumps(item)))
            for table in TABLES:
                for item in winners:
                    if item["tab"] != table or item["deleted"]:
                        continue
                    data = dict(item["data"])
                    for field, parent in RELATIONS[table].items():
                        if data[field] is not None:
                            mapping = db.execute(
                                "SELECT local_id FROM pulse_sync_records WHERE sid=? AND tab=? AND deleted=0",
                                (data[field], parent),
                            ).fetchone()
                            if not mapping:
                                raise ValueError("同步数据缺少关联记录")
                            data[field] = mapping[0]
                    if table == "calendar_task_fields" and data.get("image_path"):
                        digest = data["image_path"]
                        encoded = incoming.get("blobs", {}).get(digest)
                        if encoded is None:
                            raise ValueError("同步数据缺少图片附件")
                        name = digest + ".png"
                        self.attachments.mkdir(parents=True, exist_ok=True)
                        destination = self._image_path(name)
                        if not destination.exists():
                            destination.write_bytes(base64.b64decode(encoded, validate=True))
                        data["image_path"] = name
                    mapping = db.execute("SELECT local_id,deleted FROM pulse_sync_records WHERE sid=?", (item["sid"],)).fetchone()
                    if mapping and not mapping["deleted"]:
                        row_id = mapping["local_id"]
                        fields = ",".join(f'"{key}"=?' for key in data)
                        db.execute(f'UPDATE "{table}" SET {fields} WHERE id=?', [*data.values(), row_id])
                    else:
                        fields = ",".join(f'"{key}"' for key in data)
                        placeholders = ",".join("?" for _ in data)
                        cursor = db.execute(f'INSERT INTO "{table}" ({fields}) VALUES ({placeholders})', list(data.values()))
                        row_id = cursor.lastrowid
                    db.execute("INSERT OR REPLACE INTO pulse_sync_records VALUES(?,?,?,?,?,0)",
                               (item["sid"], table, row_id, item["version"], item["origin"]))
            for table in reversed(TABLES):
                for item in winners:
                    if item["tab"] != table or not item["deleted"]:
                        continue
                    mapping = db.execute("SELECT local_id,deleted FROM pulse_sync_records WHERE sid=?", (item["sid"],)).fetchone()
                    if mapping and not mapping["deleted"]:
                        db.execute(f'DELETE FROM "{table}" WHERE id=?', (mapping["local_id"],))
                    db.execute("INSERT OR REPLACE INTO pulse_sync_records VALUES(?,?,NULL,?,?,1)",
                               (item["sid"], table, item["version"], item["origin"]))
            db.execute("UPDATE pulse_sync_meta SET importing=0")
            return len(winners)
