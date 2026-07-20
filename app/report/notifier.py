from __future__ import annotations

import json
from pathlib import Path

from app.config.email_settings import (
    EmailSettingsError,
    build_smtp_config,
    should_prefer_email_settings,
)
from app.notification.email_sender import EmailSendError, humanize_smtp_error
from app.notification.notifier import (
    NOTIFICATION_FILE,
    NotificationConfigError,
    load_notification_config,
)
from app.report.email_sender import send_report_email
from app.report.config import load_report_config


def _normalize_recipients(recipients) -> list[str]:
    if not isinstance(recipients, list):
        return []
    return [
        str(address).strip()
        for address in recipients
        if str(address).strip()
    ]


def notify_weekly_report(
    report: dict,
    *,
    attachment_path: Path | str | None = None,
    report_config_file: Path | str | None = None,
    notification_file: Path = NOTIFICATION_FILE,
    email_settings_file: Path | str | None = None,
    send_report_email_fn=send_report_email,
) -> dict:
    if should_prefer_email_settings(email_settings_file):
        try:
            smtp_config = build_smtp_config(email_settings_file)
        except EmailSettingsError as error:
            print(f"Weekly report email notification failed: {error}")
            return {
                "sent": False,
                "skipped": False,
                "status": "Failed",
                "reason": f"Invalid email settings: {error}",
            }

        recipients = smtp_config.get("to_addresses", [])
        try:
            send_report_email_fn(
                report,
                smtp_config,
                attachment_path=attachment_path,
            )
        except EmailSendError as error:
            print(f"Weekly report email notification failed: {error}")
            return {
                "sent": False,
                "skipped": False,
                "status": "Failed",
                "reason": humanize_smtp_error(error),
                "technical_details": str(error),
            }

        return {
            "sent": True,
            "skipped": False,
            "status": "Sent",
            "reason": "Weekly report email sent.",
            "recipients": recipients,
        }

    report_config = load_report_config(report_config_file)

    if not report_config.get("email_enabled", False):
        return {
            "sent": False,
            "skipped": True,
            "status": "Disabled",
            "reason": "Report email delivery is disabled.",
        }

    recipients = _normalize_recipients(report_config.get("recipients", []))
    if not recipients:
        return {
            "sent": False,
            "skipped": True,
            "status": "Disabled",
            "reason": "No report email recipients configured.",
        }

    try:
        smtp_config = load_notification_config(notification_file)
    except (NotificationConfigError, json.JSONDecodeError) as error:
        print(f"Weekly report email notification failed: {error}")
        return {
            "sent": False,
            "skipped": False,
            "status": "Failed",
            "reason": f"Invalid notification config: {error}",
        }

    smtp_config = {
        **smtp_config,
        "to_addresses": recipients,
    }

    try:
        send_report_email_fn(
            report,
            smtp_config,
            attachment_path=attachment_path,
        )
    except EmailSendError as error:
        print(f"Weekly report email notification failed: {error}")
        return {
            "sent": False,
            "skipped": False,
            "status": "Failed",
            "reason": humanize_smtp_error(error),
            "technical_details": str(error),
        }

    return {
        "sent": True,
        "skipped": False,
        "status": "Sent",
        "reason": "Weekly report email sent.",
        "recipients": recipients,
    }
