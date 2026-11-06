"""Non-blocking IMAP sync controls and startup/periodic scheduling."""
import copy
import threading
from datetime import datetime

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from pulse.services.mail_sync import MailSync, load_secrets, save_secrets
from pulse.services.sync_store import SyncStore


class SyncControls(QWidget):
    completed = pyqtSignal(bool, str)

    def __init__(self, config_mgr, repo, parent=None):
        super().__init__(parent)
        self.config_mgr = config_mgr
        self.repo = repo
        self.busy = False
        self._closed = False
        self.store = SyncStore(repo) if repo else None
        self.directory = self.store.path.parent if self.store else config_mgr._path.parent
        secrets = load_secrets(self.directory)
        cfg = config_mgr.config.sync
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.account = QLineEdit(cfg.account or config_mgr.config.email.sender)
        self.account.setPlaceholderText("完整网易邮箱地址，例如 name@163.com")
        self.auth = QLineEdit(secrets.get("auth_code", ""))
        self.auth.setEchoMode(QLineEdit.EchoMode.Password)
        self.auth.setPlaceholderText("客户端授权码（仅保存在本机）")
        self.password = QLineEdit(secrets.get("passphrase", ""))
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("同步加密密码；留空使用授权码，各设备必须一致")
        for title, widget in (("邮箱", self.account), ("授权码", self.auth), ("同步密码", self.password)):
            row = QHBoxLayout()
            label = QLabel(title)
            label.setFixedWidth(100)
            row.addWidget(label)
            row.addWidget(widget)
            layout.addLayout(row)
        row = QHBoxLayout()
        self.auto = QCheckBox("自动同步（启动后及定时双向合并）")
        self.auto.setChecked(cfg.automatic)
        self.interval = QSpinBox()
        self.interval.setRange(1, 1440)
        self.interval.setValue(max(1, cfg.interval_minutes))
        self.interval.setSuffix(" 分钟")
        save = QPushButton("保存同步设置")
        save.clicked.connect(self.save)
        row.addWidget(self.auto)
        row.addWidget(self.interval)
        row.addWidget(save)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.buttons = []
        for title, mode in (("立即双向同步", "sync"), ("从邮箱同步", "pull"), ("用本机覆盖邮箱", "overwrite")):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, mode=mode: self.start(mode))
            row.addWidget(button)
            self.buttons.append(button)
        layout.addLayout(row)
        self.status = QLabel("未同步")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        hint = QLabel(
            "从邮箱同步会合并数据，保留本机未上传的修改。覆盖邮箱会将本机作为最新版本，"
            "其他设备再次同步时会应用这些修改及删除。旧同步邮件保留，不发送通知邮件。"
            "数据包含使用记录、任务、清单和图片，不包含 API Key 或邮箱凭据。"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.timer = QTimer(self)
        self.timer.timeout.connect(lambda: self.start("sync", automatic=True))
        self.completed.connect(self._finished)
        self._schedule()
        if cfg.automatic:
            QTimer.singleShot(3000, lambda: self.start("sync", automatic=True))
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().aboutToQuit.connect(self._shutdown)

    def _shutdown(self):
        self._closed = True
        self.timer.stop()

    def save(self):
        if self.busy:
            self.status.setText("请等待当前同步完成后保存设置")
            return False
        account = self.account.text().strip().lower()
        if account.rsplit("@", 1)[-1] not in ("163.com", "126.com", "yeah.net") or "@" not in account:
            self.status.setText("请输入完整的 163.com、126.com 或 yeah.net 邮箱地址")
            return False
        if not self.auth.text().strip():
            self.status.setText("请输入邮箱客户端授权码")
            return False
        try:
            save_secrets(self.directory, self.auth.text().strip(), self.password.text())
            cfg = self.config_mgr.config.sync
            cfg.account = account
            cfg.automatic = self.auto.isChecked()
            cfg.interval_minutes = self.interval.value()
            self.config_mgr.save()
        except OSError:
            self.status.setText("无法保存本机同步设置，请检查目录权限")
            return False
        self._schedule()
        self.status.setText("同步设置已保存")
        return True

    def _schedule(self):
        self.timer.stop()
        cfg = self.config_mgr.config.sync
        if cfg.automatic:
            self.timer.start(max(1, min(1440, cfg.interval_minutes)) * 60000)

    def start(self, mode="sync", automatic=False):
        if self.busy or self._closed:
            return
        if not self.repo:
            self.status.setText("数据库尚未初始化")
            return
        if automatic:
            cfg = self.config_mgr.config.sync
            if not cfg.automatic:
                return
            secrets = load_secrets(self.directory)
        else:
            if not self.save():
                return
            cfg = self.config_mgr.config.sync
            secrets = load_secrets(self.directory)
        if not cfg.account or not secrets.get("auth_code"):
            self.status.setText("请先保存邮箱同步设置")
            return
        if mode == "overwrite":
            reply = QMessageBox.question(
                self, "用本机覆盖邮箱",
                "邮箱同步版本将以本机为准。仅存在于邮箱的数据会标记为删除，"
                "其他设备下次同步会应用这些删除。\n旧邮件和本机备份仍会保留。是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.busy = True
        for button in self.buttons:
            button.setEnabled(False)
        self.status.setText("正在同步，请稍候…")
        config = copy.deepcopy(cfg)

        def work():
            try:
                store = self.store or SyncStore(self.repo)
                result = MailSync(store, config, secrets["auth_code"], secrets.get("passphrase", "")).run(mode)
                success = True
            except ValueError as error:
                result, success = str(error), False
            except Exception:
                # IMAP exceptions may contain server data. Do not log credentials or messages.
                result, success = "连接或同步失败，请检查网络、IMAP 服务、授权码及邮箱容量后重试", False
            if not self._closed:
                self.completed.emit(success, result)

        threading.Thread(target=work, name="pulse-mail-sync", daemon=True).start()

    def _finished(self, success, message):
        self.busy = False
        for button in self.buttons:
            button.setEnabled(True)
        self.status.setText(f"{datetime.now():%H:%M:%S} {'✓' if success else '✗'} {message}")
