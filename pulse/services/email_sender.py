"""邮件发送服务 —— 通过网易 163 SMTP 发送提醒邮件."""

import logging
import re
import smtplib
from dataclasses import dataclass
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr

logger = logging.getLogger(__name__)

# 163 SMTP 配置
SMTP_HOST = "smtp.163.com"
SMTP_PORT = 465  # SSL

_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


@dataclass
class EmailConfig:
    """邮件配置."""
    sender: str = ""          # 发送方邮箱（163）
    auth_code: str = ""       # SMTP 授权码
    recipient: str = ""       # 接收方邮箱
    enabled: bool = False

    @property
    def is_valid(self) -> bool:
        return (
            is_valid_email(self.sender)
            and bool(self.auth_code)
            and is_valid_email(self.recipient)
        )


def is_valid_email(email: str) -> bool:
    """校验邮箱格式是否合法."""
    return bool(email and _EMAIL_RE.match(email))


def send_email(cfg: EmailConfig, subject: str, content: str) -> tuple[bool, str]:
    """通过 163 SMTP 发送邮件.

    Returns:
        (成功与否, 错误信息或空串)
    """
    if not cfg.is_valid:
        return False, "邮箱配置不完整或格式不合法（需 sender / 授权码 / recipient）"

    try:
        msg = MIMEText(content, "plain", "utf-8")
        msg["From"] = formataddr((str(Header("Pulse", "utf-8")), cfg.sender))
        msg["To"] = cfg.recipient
        msg["Subject"] = Header(subject, "utf-8")

        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.login(cfg.sender, cfg.auth_code)
            server.sendmail(cfg.sender, [cfg.recipient], msg.as_string())

        logger.info("提醒邮件已发送: %s → %s", cfg.sender, cfg.recipient)
        return True, ""
    except smtplib.SMTPAuthenticationError as e:
        logger.error("SMTP 认证失败（授权码错误）: %s", e)
        return False, f"SMTP 认证失败，请检查授权码（{e.smtp_code}）"
    except Exception as e:
        logger.error("发送邮件失败: %s", e)
        return False, f"发送失败: {e}"
