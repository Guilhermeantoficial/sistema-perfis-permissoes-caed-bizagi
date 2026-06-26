from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import settings


class EmailConfigurationError(RuntimeError):
    pass


class EmailClient:
    def validate_configuration(self) -> list[str]:
        missing = []
        if not settings.smtp_host:
            missing.append("SMTP_HOST")
        if not settings.smtp_from:
            missing.append("SMTP_FROM")
        return missing

    def send(self, *, recipient: str, subject: str, body: str) -> None:
        if not settings.smtp_enabled:
            raise EmailConfigurationError("SMTP desativado.")
        missing = self.validate_configuration()
        if missing:
            raise EmailConfigurationError("Configuração SMTP incompleta: " + ", ".join(missing))
        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        smtp_cls = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
        with smtp_cls(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            if settings.smtp_starttls and not settings.smtp_use_ssl:
                server.starttls()
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            server.send_message(message)
