from __future__ import annotations

import os
import smtplib
import socket
import ssl
from contextlib import contextmanager
from email.mime.text import MIMEText

from app.core.logging import get_logger

logger = get_logger(__name__)

SMTP_TIMEOUT = 30


class EmailSendError(RuntimeError):
    pass


def resolve_smtp_password(smtp_config: dict) -> str:
    direct_password = smtp_config.get("smtp_password")
    if direct_password:
        return str(direct_password)

    password_env = smtp_config.get("smtp_password_env", "SMTP_PASSWORD")
    return os.getenv(password_env, "")


def smtp_uses_ssl(smtp_config: dict) -> bool:
    return bool(smtp_config.get("use_ssl", False))


def smtp_uses_starttls(smtp_config: dict) -> bool:
    if smtp_uses_ssl(smtp_config):
        return False
    return bool(smtp_config.get("use_tls", True))


def log_smtp_connection_attempt(smtp_config: dict) -> None:
    password = resolve_smtp_password(smtp_config)
    logger.info(
        "SMTP connection attempt: provider=%s smtp_host=%s smtp_port=%s "
        "use_ssl=%s use_tls=%s username_present=%s password_configured=%s",
        smtp_config.get("provider", "unknown"),
        smtp_config.get("smtp_host"),
        smtp_config.get("smtp_port"),
        smtp_uses_ssl(smtp_config),
        smtp_uses_starttls(smtp_config),
        bool(str(smtp_config.get("smtp_username", "")).strip()),
        bool(str(password).strip()),
    )


def unwrap_smtp_exception(error: BaseException) -> BaseException:
    current: BaseException = error
    while isinstance(current, EmailSendError) and current.__cause__ is not None:
        current = current.__cause__
    return current


def humanize_smtp_error(error: Exception | str) -> str:
    if isinstance(error, str):
        return _humanize_smtp_error_message(error)

    root = unwrap_smtp_exception(error)
    if isinstance(root, smtplib.SMTPAuthenticationError):
        return (
            "SMTP authentication failed. Check the email address, password, "
            "authorization password, or SMTP permission."
        )
    if isinstance(root, smtplib.SMTPNotSupportedError):
        return "The SMTP server does not support the selected security mode."
    if isinstance(root, smtplib.SMTPSenderRefused):
        return "The SMTP server rejected the sender address."
    if isinstance(root, smtplib.SMTPRecipientsRefused):
        return "One or more recipients were rejected by the SMTP server."
    if isinstance(root, smtplib.SMTPDataError):
        return "The SMTP server rejected the message content."
    if isinstance(root, ssl.SSLCertVerificationError):
        return (
            "SMTP SSL certificate verification failed. The server may use "
            "an internal company certificate."
        )
    if isinstance(root, ssl.SSLError):
        return (
            "SSL connection failed. Check SSL/STARTTLS mode and "
            "certificate configuration."
        )
    if isinstance(root, socket.gaierror):
        return "Unable to resolve the SMTP server hostname."
    if isinstance(root, ConnectionRefusedError):
        return "The SMTP server refused the connection."
    if isinstance(root, (TimeoutError, socket.timeout)):
        return (
            "Unable to connect to the SMTP server. Check the SMTP host, port, "
            "network, firewall, VPN, and SSL/TLS mode."
        )

    return _humanize_smtp_error_message(str(root))


def _humanize_smtp_error_message(message: str) -> str:
    cleaned = str(message).strip()
    if cleaned.lower().startswith("email send failed:"):
        cleaned = cleaned.split(":", 1)[1].strip()

    lowered = cleaned.lower()
    if any(
        marker in lowered
        for marker in (
            "certificate verify failed",
            "certificate_verify_failed",
            "self signed certificate",
        )
    ):
        return (
            "SMTP SSL certificate verification failed. The server may use "
            "an internal company certificate."
        )
    if any(
        marker in lowered
        for marker in (
            "authentication failed",
            "invalid credentials",
            "535",
            "534",
        )
    ):
        return (
            "SMTP authentication failed. Check the email address, password, "
            "authorization password, or SMTP permission."
        )
    if "not supported" in lowered and "starttls" in lowered:
        return "The SMTP server does not support the selected security mode."
    if any(
        marker in lowered
        for marker in (
            "name or service not known",
            "getaddrinfo failed",
            "nodename nor servname provided",
            "gaierror",
        )
    ):
        return "Unable to resolve the SMTP server hostname."
    if "connection refused" in lowered:
        return "The SMTP server refused the connection."
    if any(
        marker in lowered
        for marker in (
            "timed out",
            "timeout",
            "10060",
        )
    ):
        return (
            "Unable to connect to the SMTP server. Check the SMTP host, port, "
            "network, firewall, VPN, and SSL/TLS mode."
        )
    if any(
        marker in lowered
        for marker in ("ssl", "wrong version number", "tlsv1", "sslv3")
    ):
        return (
            "SSL connection failed. Check SSL/STARTTLS mode and "
            "certificate configuration."
        )
    if any(marker in lowered for marker in ("starttls", "tls negotiation")):
        return "The SMTP server does not support the selected security mode."
    if "message content rejected" in lowered or "smtpdataerror" in lowered:
        return "The SMTP server rejected the message content."
    if "sender address rejected" in lowered or "sender rejected" in lowered:
        return "The SMTP server rejected the sender address."
    if "recipient rejected" in lowered or "recipients refused" in lowered:
        return "One or more recipients were rejected by the SMTP server."
    return "The report email could not be delivered."


def log_smtp_failure(smtp_config: dict, error: Exception) -> None:
    root = unwrap_smtp_exception(error)
    logger.exception(
        "SMTP delivery failed (%s): host=%s port=%s use_ssl=%s use_tls=%s",
        type(root).__name__,
        smtp_config.get("smtp_host"),
        smtp_config.get("smtp_port"),
        smtp_uses_ssl(smtp_config),
        smtp_uses_starttls(smtp_config),
        exc_info=error,
    )


@contextmanager
def create_smtp_connection(smtp_config: dict):
    host = smtp_config["smtp_host"]
    port = int(smtp_config["smtp_port"])
    ssl_context = ssl.create_default_context()
    server = None

    try:
        if smtp_uses_ssl(smtp_config):
            server = smtplib.SMTP_SSL(
                host,
                port,
                timeout=SMTP_TIMEOUT,
                context=ssl_context,
            )
        else:
            server = smtplib.SMTP(host, port, timeout=SMTP_TIMEOUT)
            if smtp_uses_starttls(smtp_config):
                server.ehlo()
                server.starttls(context=ssl_context)
                server.ehlo()
        yield server
    finally:
        if server is not None:
            try:
                server.quit()
            except Exception:
                try:
                    server.close()
                except Exception:
                    pass


def send_smtp_message(
    smtp_config: dict,
    *,
    from_address: str,
    to_addresses: list[str],
    message_content: str,
) -> None:
    password = resolve_smtp_password(smtp_config)
    username = smtp_config.get("smtp_username", "")

    try:
        log_smtp_connection_attempt(smtp_config)
        with create_smtp_connection(smtp_config) as server:
            if username or password:
                server.login(username, password)
            server.sendmail(from_address, to_addresses, message_content)
    except Exception as error:
        log_smtp_failure(smtp_config, error)
        raise EmailSendError(str(error)) from error


def send_email(
    smtp_config: dict,
    subject: str,
    body: str,
) -> None:
    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = smtp_config["from_address"]
    message["To"] = ", ".join(smtp_config["to_addresses"])

    send_smtp_message(
        smtp_config,
        from_address=smtp_config["from_address"],
        to_addresses=smtp_config["to_addresses"],
        message_content=message.as_string(),
    )
