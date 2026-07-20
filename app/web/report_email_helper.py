from __future__ import annotations

import json
import os
from pathlib import Path

from app.config.validator import validate_configuration
from app.notification.notifier import (
    NOTIFICATION_FILE,
    NotificationConfigError,
    load_notification_config,
)
from app.report.config import load_report_config

DISPLAY_STATUSES = {
    "Disabled",
    "Not Configured",
    "Ready",
    "Sent",
    "Failed",
}

STATUS_MESSAGES = {
    "Disabled": "Report email delivery is turned off.",
    "Not Configured": "SMTP email is not configured yet.",
    "Ready": "Email delivery is configured and ready for the next report.",
    "Sent": "The latest report email was sent successfully.",
    "Failed": "The report email could not be delivered.",
}


def _email_delivery_enabled(report_config: dict) -> bool:
    if not report_config.get("email_enabled", False):
        return False
    recipients = report_config.get("recipients", [])
    return bool(recipients)


def _smtp_configuration_details(
    *,
    notification_file: Path,
    environ: dict[str, str] | None = None,
) -> str | None:
    config_result = validate_configuration(environ)
    missing_smtp = any(
        warning.startswith("SMTP_PASSWORD is not set")
        for warning in config_result.get("warnings", [])
    )
    if missing_smtp:
        return "SMTP_PASSWORD is not set."

    if not notification_file.exists():
        return f"Notification config not found: {notification_file}"

    try:
        load_notification_config(notification_file)
    except (NotificationConfigError, json.JSONDecodeError) as error:
        return str(error)

    return None


def _is_configuration_failure(reason: str) -> bool:
    normalized = reason.strip().lower()
    if not normalized:
        return False

    configuration_markers = (
        "invalid notification config",
        "notification config not found",
        "missing required notification",
        "smtp_password",
        "must be a json object",
        "must be a non-empty list",
    )
    return any(marker in normalized for marker in configuration_markers)


def _extract_notification_details(report: dict | None) -> tuple[str, str, bool, bool]:
    if not report:
        return "", "", False, False

    notification = report.get("email_notification") or {}
    stored_status = str(report.get("email_status", "")).strip()
    reason = str(notification.get("reason", "")).strip()
    sent = bool(notification.get("sent"))
    skipped = bool(notification.get("skipped"))

    if stored_status not in DISPLAY_STATUSES:
        if reason:
            stored_status = "Failed"
        elif skipped:
            stored_status = "Disabled"
        else:
            stored_status = ""

    notification_status = str(notification.get("status", "")).strip()
    if notification_status in DISPLAY_STATUSES:
        stored_status = notification_status

    return stored_status, reason, sent, skipped


def resolve_report_email_display(
    report: dict | None,
    *,
    report_config_file: Path | str | None = None,
    notification_file: Path | str | None = None,
    environ: dict[str, str] | None = None,
) -> dict:
    report_config = load_report_config(report_config_file)
    notification_path = (
        Path(notification_file)
        if notification_file is not None
        else NOTIFICATION_FILE
    )
    env = dict(os.environ if environ is None else environ)

    if not _email_delivery_enabled(report_config):
        return {
            "display_status": "Disabled",
            "status_message": STATUS_MESSAGES["Disabled"],
            "status_details": None,
        }

    configuration_details = _smtp_configuration_details(
        notification_file=notification_path,
        environ=env,
    )
    if configuration_details:
        return {
            "display_status": "Not Configured",
            "status_message": STATUS_MESSAGES["Not Configured"],
            "status_details": configuration_details,
        }

    stored_status, reason, sent, skipped = _extract_notification_details(report)

    if sent or stored_status == "Sent":
        return {
            "display_status": "Sent",
            "status_message": STATUS_MESSAGES["Sent"],
            "status_details": reason or None,
        }

    if stored_status == "Failed":
        if _is_configuration_failure(reason):
            return {
                "display_status": "Not Configured",
                "status_message": STATUS_MESSAGES["Not Configured"],
                "status_details": reason or None,
            }
        return {
            "display_status": "Failed",
            "status_message": STATUS_MESSAGES["Failed"],
            "status_details": reason or None,
        }

    if stored_status == "Disabled" or skipped:
        return {
            "display_status": "Ready",
            "status_message": STATUS_MESSAGES["Ready"],
            "status_details": reason or None,
        }

    return {
        "display_status": "Ready",
        "status_message": STATUS_MESSAGES["Ready"],
        "status_details": None,
    }
