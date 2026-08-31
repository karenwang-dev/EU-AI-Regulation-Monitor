from __future__ import annotations

import json
from pathlib import Path

from app.config.email_settings import (
    EmailSettingsError,
    build_smtp_config,
    resolve_email_settings_path,
    should_prefer_email_settings,
)
from app.notification.notifier import (
    NOTIFICATION_FILE,
    NotificationConfigError,
    load_notification_config,
)
from app.report.config import load_report_config


def normalize_recipients(recipients) -> list[str]:
    if not isinstance(recipients, list):
        return []
    return [
        str(address).strip()
        for address in recipients
        if str(address).strip()
    ]


def resolve_report_smtp_config(
    *,
    report_config_file: Path | str | None = None,
    notification_file: Path | str | None = None,
    email_settings_file: Path | str | None = None,
) -> dict:
    """Build an SMTP config dict for report delivery."""
    settings_path = resolve_email_settings_path(email_settings_file)
    if should_prefer_email_settings(settings_path):
        return build_smtp_config(settings_path)

    report_config = load_report_config(report_config_file)
    recipients = normalize_recipients(report_config.get("recipients", []))
    notification_path = (
        Path(notification_file)
        if notification_file is not None
        else NOTIFICATION_FILE
    )
    smtp_config = load_notification_config(notification_path)
    return {
        **smtp_config,
        "to_addresses": recipients,
    }


def resolve_report_delivery_readiness(
    *,
    report_config_file: Path | str | None = None,
    notification_file: Path | str | None = None,
    email_settings_file: Path | str | None = None,
) -> tuple[dict | None, dict | None]:
    """Return ``(smtp_config, None)`` when ready, or ``(None, result)`` to skip."""
    settings_path = resolve_email_settings_path(email_settings_file)
    if should_prefer_email_settings(settings_path):
        try:
            return resolve_report_smtp_config(
                report_config_file=report_config_file,
                notification_file=notification_file,
                email_settings_file=email_settings_file,
            ), None
        except EmailSettingsError as error:
            return None, {
                "sent": False,
                "skipped": False,
                "status": "Failed",
                "reason": f"Invalid email settings: {error}",
            }

    report_config = load_report_config(report_config_file)
    if not report_config.get("email_enabled", False):
        return None, {
            "sent": False,
            "skipped": True,
            "status": "Disabled",
            "reason": "Report email delivery is disabled.",
        }

    recipients = normalize_recipients(report_config.get("recipients", []))
    if not recipients:
        return None, {
            "sent": False,
            "skipped": True,
            "status": "Disabled",
            "reason": "No report email recipients configured.",
        }

    notification_path = (
        Path(notification_file)
        if notification_file is not None
        else NOTIFICATION_FILE
    )
    try:
        smtp_config = resolve_report_smtp_config(
            report_config_file=report_config_file,
            notification_file=notification_path,
            email_settings_file=email_settings_file,
        )
    except (NotificationConfigError, json.JSONDecodeError) as error:
        return None, {
            "sent": False,
            "skipped": False,
            "status": "Failed",
            "reason": f"Invalid notification config: {error}",
        }

    return smtp_config, None
