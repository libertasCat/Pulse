"""Encrypted, chunked snapshots in a dedicated IMAP folder; no SMTP delivery."""
import base64
import gzip
import hashlib
import imaplib
import io
import json
import os
import ssl
import threading
import uuid
from contextlib import contextmanager
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from pulse.services.sync_store import MAX_BYTES, SyncStore

PROTOCOL = "pulse-sync-v1"
CHUNK = 2 * 1024 * 1024


def load_secrets(directory):
    path = Path(directory) / "sync-secrets.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"auth_code": "", "passphrase": ""}
        except (OSError, ValueError):
            return {"auth_code": "", "passphrase": ""}
    # Source runs can import the user's local authorization code without logging it.
    source = Path(__file__).resolve().parents[2] / "authroize.txt"
    if source.is_file():
        return {"auth_code": source.read_text(encoding="utf-8").strip(), "passphrase": ""}
    return {"auth_code": "", "passphrase": ""}


def save_secrets(directory, auth_code, passphrase):
    path = Path(directory) / "sync-secrets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump({"auth_code": auth_code, "passphrase": passphrase}, stream)
    temp.chmod(0o600)
    temp.replace(path)


def cipher(account, password):
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                    salt=("pulse-sync-v1:" + account.lower()).encode(),
                    iterations=310000).derive(password.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def encode_snapshot(snapshot, encryption):
    raw = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode()
    if len(raw) > MAX_BYTES:
        raise ValueError("同步数据超过 20 MB，请清理旧记录或减少图片后重试")
    return encryption.encrypt(gzip.compress(raw))


def decode_snapshot(token, encryption):
    if len(token) > MAX_BYTES * 2:
        raise ValueError("同步邮件过大")
    try:
        compressed = encryption.decrypt(token)
    except InvalidToken:
        raise ValueError("无法解密邮箱数据，请确认所有设备使用相同的同步密码") from None
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("同步数据超过大小限制")
    snapshot = json.loads(raw)
    SyncStore.validate(snapshot)
    return snapshot


class MailSync:
    def __init__(self, store, config, auth_code, passphrase="", client_factory=imaplib.IMAP4_SSL):
        self.store = store
        self.config = config
        self.auth_code = auth_code
        self.encryption = cipher(config.account, passphrase or auth_code)
        self.client_factory = client_factory
        self.lock = threading.Lock()

    @contextmanager
    def connection(self):
        cfg = self.config
        hosts = {"163.com": "imap.163.com", "126.com": "imap.126.com", "yeah.net": "imap.yeah.net"}
        domain = cfg.account.rsplit("@", 1)[-1].lower()
        if domain not in hosts or not self.auth_code:
            raise ValueError("请填写完整的网易邮箱地址和客户端授权码")
        client = self.client_factory(hosts[domain], 993, ssl_context=ssl.create_default_context(), timeout=30)
        try:
            client.login(cfg.account, self.auth_code)
            if "ID" in {c.decode() if isinstance(c, bytes) else c for c in client.capabilities}:
                imaplib.Commands.setdefault("ID", ("AUTH",))
                kind, _ = client._simple_command("ID", '("name" "Pulse" "version" "1.0" "vendor" "Pulse")')
                if kind != "OK":
                    raise ValueError("网易邮箱客户端身份验证失败")
            # Fixed ASCII folder: never issue STORE, DELETE or EXPUNGE against user mail.
            folder = "PulseSync"
            kind, _ = client.select(folder)
            if kind != "OK":
                kind, _ = client.create(folder)
                if kind != "OK":
                    raise ValueError("无法创建 PulseSync 同步文件夹")
                kind, _ = client.select(folder)
            if kind != "OK":
                raise ValueError("无法打开 PulseSync，请检查 IMAP 服务是否开启")
            yield client
        finally:
            try:
                client.logout()
            except Exception:
                pass

    @staticmethod
    def _ok(result, message):
        kind, data = result
        if kind != "OK":
            raise ValueError(message)
        return data

    def download(self, client):
        # NetEase accepts HEADER searches on custom fields but returns no matches.
        # The dedicated folder is small; filter verified headers on the client instead.
        data = self._ok(client.uid("search", None, "ALL"), "查询同步邮件失败")
        uids = data[0].split() if data and data[0] else []
        if len(uids) > 10000:
            raise ValueError("同步历史超过 10000 封，请归档 PulseSync 中的旧邮件")
        groups = {}
        for uid in uids:
            response = self._ok(client.uid("fetch", uid, "(BODY.PEEK[HEADER] RFC822.SIZE)"), "读取同步索引失败")
            literals = [part[1] for part in response if isinstance(part, tuple)]
            if not literals:
                raise ValueError("同步邮件头不完整")
            header = BytesParser(policy=policy.default).parsebytes(literals[0])
            if header.get("X-Pulse-Protocol") != PROTOCOL:
                continue
            try:
                bundle = str(uuid.UUID(header["X-Pulse-Bundle"]))
                device = str(uuid.UUID(header["X-Pulse-Device"]))
                index = int(header["X-Pulse-Part"])
                total = int(header["X-Pulse-Parts"])
                if not 1 <= index <= total <= 20:
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                raise ValueError("同步邮件索引损坏") from None
            group = groups.setdefault(bundle, {"device": device, "total": total, "parts": {}, "latest": 0})
            if group["device"] != device or group["total"] != total:
                raise ValueError("同步分片索引不一致")
            group["parts"][index] = uid
            group["latest"] = max(group["latest"], int(uid))
        # An interrupted APPEND cannot replace the preceding complete snapshot.
        latest = {}
        for group in groups.values():
            if len(group["parts"]) == group["total"]:
                old = latest.get(group["device"])
                if old is None or group["latest"] > old["latest"]:
                    latest[group["device"]] = group
        combined = {"schema": 1, "device": self.store.device, "records": {}, "blobs": {}}
        for group in latest.values():
            chunks = []
            for index in range(1, group["total"] + 1):
                uid = group["parts"][index]
                # Reject oversized messages before fetching their bodies.
                response = self._ok(client.uid("fetch", uid, "(RFC822.SIZE)"), "读取邮件大小失败")
                import re
                metadata = b" ".join(x for x in response if isinstance(x, bytes))
                size = re.search(rb"RFC822.SIZE (\d+)", metadata)
                if not size or int(size[1]) > CHUNK * 2 + 4096:
                    raise ValueError("同步邮件大小异常")
                response = self._ok(client.uid("fetch", uid, "(BODY.PEEK[])"), "下载同步数据失败")
                literals = [part[1] for part in response if isinstance(part, tuple)]
                if not literals:
                    raise ValueError("同步数据不完整")
                message = BytesParser(policy=policy.default).parsebytes(literals[0])
                raw = message.get_payload(decode=True)
                if raw is None or len(raw) > CHUNK or hashlib.sha256(raw).hexdigest() != str(message["X-Pulse-SHA256"]).strip():
                    raise ValueError("同步分片校验失败")
                chunks.append(raw)
            snapshot = decode_snapshot(b"".join(chunks), self.encryption)
            for sid, item in snapshot["records"].items():
                old = combined["records"].get(sid)
                if old is None or SyncStore.rank(item) > SyncStore.rank(old):
                    combined["records"][sid] = item
            combined["blobs"].update(snapshot.get("blobs", {}))
        return combined

    def upload(self, client, snapshot):
        token = encode_snapshot(snapshot, self.encryption)
        chunks = [token[i:i + CHUNK] for i in range(0, len(token), CHUNK)]
        bundle = str(uuid.uuid4())
        for index, chunk in enumerate(chunks, 1):
            message = EmailMessage()
            message["From"] = self.config.account
            message["To"] = self.config.account
            message["Subject"] = "Pulse encrypted sync"
            message["X-Pulse-Protocol"] = PROTOCOL
            message["X-Pulse-Bundle"] = bundle
            message["X-Pulse-Device"] = str(uuid.UUID(self.store.device))
            message["X-Pulse-Part"] = str(index)
            message["X-Pulse-Parts"] = str(len(chunks))
            message["X-Pulse-SHA256"] = hashlib.sha256(chunk).hexdigest()
            message.set_content(chunk, maintype="application", subtype="octet-stream")
            self._ok(client.append("PulseSync", r"\Seen", None, message.as_bytes(policy=policy.SMTP)),
                     "上传同步数据失败，旧邮箱数据已保留")

    def run(self, mode="sync"):
        if mode not in ("sync", "pull", "overwrite"):
            raise ValueError("未知同步模式")
        if not self.lock.acquire(blocking=False):
            raise ValueError("同步正在进行")
        try:
            with self.connection() as client:
                incoming = self.download(client)
                count = self.store.merge(incoming, overwrite=mode == "overwrite")
                if mode != "pull":
                    snapshot = self.store.snapshot()
                    if mode == "overwrite" or snapshot["records"] != incoming["records"]:
                        self.upload(client, snapshot)
                return f"同步完成，合并 {count} 条记录" if mode != "overwrite" else "已用本机数据覆盖邮箱同步版本，旧邮件保留供恢复"
        finally:
            self.lock.release()
