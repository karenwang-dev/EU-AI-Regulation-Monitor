from __future__ import annotations

import json
import os
import re
from pathlib import Path

from app.config.email_settings import (
    EmailSettingsError,
    TEST_EMAIL_BODY,
    TEST_EMAIL_SUBJECT,
    build_smtp_config,
    contains_stored_password,
    is_email_settings_active,
    load_email_settings,
    load_email_settings_public,
    resolve_email_settings_path,
    security_mode_label,
    should_prefer_email_settings,
)
from app.config.validator import validate_configuration
from app.core.logging import get_logger
from app.notification.email_sender import (
    EmailSendError,
    humanize_smtp_error,
    send_email,
)
from app.notification.notifier import (
    NOTIFICATION_FILE,
    NotificationConfigError,
    load_notification_config,
)
from app.report.config import load_report_config
from app.report.notifier import notify_weekly_report
from app.report.storage import DEFAULT_REPORTS_DIR, update_report

logger = get_logger(__name__)

DISPLAY_STATUSES = {
    "Disabled",
    "Not Configured",
    "Ready",
    "Sending",
    "Sent",
    "Failed",
}

STATUS_MESSAGES = {
    "Disabled": "Report email delivery is turned off.",
    "Not Configured": "SMTP email is not configured yet.",
    "Ready": "Email delivery is configured and ready to send.",
    "Sending": "Sending report email...",
    "Sent": "The latest report email was sent successfully.",
    "Failed": "The report email could not be delivered.",
}


def _email_delivery_enabled(
    report_config: dict,
    *,
    email_settings_file: Path | str | None = None,
) -> bool:
    if is_email_settings_active(email_settings_file):
        return True

    if not report_config.get("email_enabled", False):
        return False
    recipients = report_config.get("recipients", [])
    return bool(recipients)


def sanitize_log_message(
    message: str,
    *,
    email_settings_file: Path | str | None = None,
) -> str:
    sanitized = str(message)
    for key, value in os.environ.items():
        if not value:
            continue
        if any(token in key.upper() for token in ("PASSWORD", "SECRET", "API_KEY")):
            sanitized = sanitized.replace(value, "[REDACTED]")

    settings_path = (
        resolve_email_settings_path(email_settings_file)
        if email_settings_file is not None
        else None
    )
    if settings_path and is_email_settings_active(settings_path):
        try:
            settings = load_email_settings(settings_path)
            password = settings.get("password", "")
            if password:
                sanitized = sanitized.replace(password, "[REDACTED]")
        except EmailSettingsError:
            pass

    return sanitized


def _smtp_configuration_details(
    *,
    notification_file: Path,
    email_settings_file: Path | str | None = None,
    environ: dict[str, str] | None = None,
) -> str | None:
    settings_path = resolve_email_settings_path(email_settings_file)
    if should_prefer_email_settings(settings_path):
        try:
            build_smtp_config(settings_path)
            return None
        except EmailSettingsError as error:
            return str(error)

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
        smtp_config = load_notification_config(notification_file)
    except (NotificationConfigError, json.JSONDecodeError) as error:
        return str(error)

    missing_fields = []
    if not str(smtp_config.get("smtp_host", "")).strip():
        missing_fields.append("smtp_host")
    if smtp_config.get("smtp_port") in (None, ""):
        missing_fields.append("smtp_port")
    if not str(smtp_config.get("from_address", "")).strip():
        missing_fields.append("from_address")
    if missing_fields:
        return f"Missing required SMTP settings: {', '.join(missing_fields)}"

    return None


def _is_configuration_failure(reason: str) -> bool:
    normalized = reason.strip().lower()
    if not normalized:
        return False

    configuration_markers = (
        "invalid notification config",
        "notification config not found",
        "invalid email settings",
        "missing required notification",
        "missing required smtp settings",
        "smtp_password",
        "app password is required",
        "email settings",
        "must be a json object",
        "must be a non-empty list",
        "no report email recipients configured",
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


def build_email_config_summary(
    *,
    report_config_file: Path | str | None = None,
    notification_file: Path | str | None = None,
    email_settings_file: Path | str | None = None,
    environ: dict[str, str] | None = None,
) -> dict:
    settings_path = resolve_email_settings_path(email_settings_file)
    if should_prefer_email_settings(settings_path):
        public = load_email_settings_public(settings_path)
        configuration_details = _smtp_configuration_details(
            notification_file=Path(notification_file or NOTIFICATION_FILE),
            email_settings_file=settings_path,
            environ=dict(os.environ if environ is None else environ),
        )
        return {
            "email_enabled": public["configured"] or bool(public["recipients"]),
            "smtp_host": public["smtp_host"],
            "smtp_port": str(public["smtp_port"]),
            "sender_address": public["username"] or "N/A",
            "recipients": public["recipients"],
            "tls_mode": security_mode_label(
                public.get("use_ssl", False),
                public.get("use_tls", True),
            ),
            "configuration_complete": public["configured"]
            and configuration_details is None,
        }

    report_config = load_report_config(report_config_file)
    notification_path = (
        Path(notification_file)
        if notification_file is not None
        else NOTIFICATION_FILE
    )
    env = dict(os.environ if environ is None else environ)

    summary = {
        "email_enabled": bool(report_config.get("email_enabled", False)),
        "smtp_host": "N/A",
        "smtp_port": "N/A",
        "sender_address": "N/A",
        "recipients": report_config.get("recipients", []),
        "tls_mode": "N/A",
    }

    if notification_path.exists():
        try:
            smtp_config = load_notification_config(notification_path)
            summary["smtp_host"] = str(smtp_config.get("smtp_host", "N/A"))
            summary["smtp_port"] = str(smtp_config.get("smtp_port", "N/A"))
            summary["sender_address"] = str(smtp_config.get("from_address", "N/A"))
            summary["tls_mode"] = security_mode_label(
                bool(smtp_config.get("use_ssl", False)),
                bool(smtp_config.get("use_tls", True)),
            )
        except (NotificationConfigError, json.JSONDecodeError):
            pass

    configuration_details = _smtp_configuration_details(
        notification_file=notification_path,
        email_settings_file=settings_path,
        environ=env,
    )
    summary["configuration_complete"] = (
        summary["email_enabled"]
        and bool(summary["recipients"])
        and configuration_details is None
    )
    return summary


def build_email_action_flags(
    report: dict | None,
    email_display: dict,
) -> dict:
    status = email_display.get("display_status", "Disabled")
    report_id = report.get("id") if report else None
    return {
        "report_id": report_id,
        "can_send": bool(report_id) and status == "Ready",
        "can_retry": bool(report_id) and status == "Failed",
        "can_test": status not in {"Disabled", "Not Configured"},
    }


def resolve_report_email_display(
    report: dict | None,
    *,
    report_config_file: Path | str | None = None,
    notification_file: Path | str | None = None,
    email_settings_file: Path | str | None = None,
    environ: dict[str, str] | None = None,
) -> dict:
    report_config = load_report_config(report_config_file)
    notification_path = (
        Path(notification_file)
        if notification_file is not None
        else NOTIFICATION_FILE
    )
    settings_path = resolve_email_settings_path(email_settings_file)
    env = dict(os.environ if environ is None else environ)

    if not _email_delivery_enabled(
        report_config,
        email_settings_file=settings_path,
    ):
        return {
            "display_status": "Disabled",
            "status_message": STATUS_MESSAGES["Disabled"],
            "status_details": None,
        }

    configuration_details = _smtp_configuration_details(
        notification_file=notification_path,
        email_settings_file=settings_path,
        environ=env,
    )
    if configuration_details:
        return {
            "display_status": "Not Configured",
            "status_message": STATUS_MESSAGES["Not Configured"],
            "status_details": configuration_details,
        }

    stored_status, reason, sent, skipped = _extract_notification_details(report)
    notification = (report or {}).get("email_notification") or {}
    technical_details = str(notification.get("technical_details", "")).strip() or reason

    if stored_status == "Sending":
        return {
            "display_status": "Sending",
            "status_message": STATUS_MESSAGES["Sending"],
            "status_details": None,
        }

    if sent or stored_status == "Sent":
        return {
            "display_status": "Sent",
            "status_message": STATUS_MESSAGES["Sent"],
            "status_details": technical_details or None,
        }

    if stored_status == "Failed":
        if _is_configuration_failure(reason):
            return {
                "display_status": "Not Configured",
                "status_message": STATUS_MESSAGES["Not Configured"],
                "status_details": technical_details or reason or None,
            }
        human_message = (
            reason
            if notification.get("technical_details")
            else humanize_smtp_error(reason)
        )
        return {
            "display_status": "Failed",
            "status_message": human_message or STATUS_MESSAGES["Failed"],
            "status_details": technical_details or None,
        }

    if stored_status == "Disabled" or skipped:
        return {
            "display_status": "Ready",
            "status_message": STATUS_MESSAGES["Ready"],
            "status_details": technical_details or None,
        }

    return {
        "display_status": "Ready",
        "status_message": STATUS_MESSAGES["Ready"],
        "status_details": None,
    }


def _build_smtp_config_for_delivery(
    *,
    report_config_file: Path | str | None,
    notification_file: Path | str,
    email_settings_file: Path | str | None = None,
) -> dict:
    settings_path = resolve_email_settings_path(email_settings_file)
    if should_prefer_email_settings(settings_path):
        return build_smtp_config(settings_path)

    report_config = load_report_config(report_config_file)
    recipients = report_config.get("recipients", [])
    smtp_config = load_notification_config(notification_file)
    return {
        **smtp_config,
        "to_addresses": recipients,
    }


def _finalize_notification_result(
    result: dict,
    *,
    email_settings_file: Path | str | None = None,
) -> dict:
    if result.get("status") != "Failed":
        return result

    technical_details = str(result.get("technical_details", "")).strip()
    if not technical_details:
        technical_details = str(result.get("reason", "")).strip()

    logger.exception(
        "Report email delivery failed: %s",
        sanitize_log_message(
            technical_details,
            email_settings_file=email_settings_file,
        ),
    )
    reason = str(result.get("reason", "")).strip()
    if technical_details and reason == technical_details:
        reason = humanize_smtp_error(technical_details)
    return {
        **result,
        "technical_details": technical_details,
        "reason": reason,
    }


def deliver_report_email(
    report: dict,
    *,
    reports_dir: Path | str | None = None,
    report_config_file: Path | str | None = None,
    notification_file: Path | str | None = None,
    email_settings_file: Path | str | None = None,
    notify_weekly_report_fn=notify_weekly_report,
    update_report_fn=update_report,
) -> dict:
    display = resolve_report_email_display(
        report,
        report_config_file=report_config_file,
        notification_file=notification_file,
        email_settings_file=email_settings_file,
    )
    if display["display_status"] == "Disabled":
        raise ValueError("Report email delivery is disabled.")
    if display["display_status"] == "Not Configured":
        raise ValueError("SMTP email is not configured.")

    reports_root = (
        Path(reports_dir) if reports_dir is not None else DEFAULT_REPORTS_DIR
    )
    attachment_path = reports_root / report["filename"]
    notification_path = (
        Path(notification_file)
        if notification_file is not None
        else NOTIFICATION_FILE
    )

    notification_result = notify_weekly_report_fn(
        report,
        attachment_path=attachment_path,
        report_config_file=report_config_file,
        notification_file=notification_path,
        email_settings_file=email_settings_file,
    )
    notification_result = _finalize_notification_result(
        notification_result,
        email_settings_file=email_settings_file,
    )

    return update_report_fn(
        {
            **report,
            "email_status": notification_result.get("status", "Failed"),
            "email_notification": notification_result,
        },
        reports_dir=reports_dir,
    )


def send_test_report_email(
    *,
    report_config_file: Path | str | None = None,
    notification_file: Path | str | None = None,
    email_settings_file: Path | str | None = None,
    send_email_fn=send_email,
) -> dict:
    display = resolve_report_email_display(
        None,
        report_config_file=report_config_file,
        notification_file=notification_file,
        email_settings_file=email_settings_file,
    )
    if display["display_status"] == "Disabled":
        return {
            "ok": False,
            "message": STATUS_MESSAGES["Disabled"],
        }
    if display["display_status"] == "Not Configured":
        return {
            "ok": False,
            "message": STATUS_MESSAGES["Not Configured"],
            "technical_details": display.get("status_details"),
        }

    notification_path = (
        Path(notification_file)
        if notification_file is not None
        else NOTIFICATION_FILE
    )

    try:
        smtp_config = _build_smtp_config_for_delivery(
            report_config_file=report_config_file,
            notification_file=notification_path,
            email_settings_file=email_settings_file,
        )
        send_email_fn(
            smtp_config,
            TEST_EMAIL_SUBJECT,
            TEST_EMAIL_BODY,
        )
    except (EmailSendError, NotificationConfigError, EmailSettingsError) as error:
        technical_details = str(error)
        logger.exception(
            "Report test email failed: %s",
            sanitize_log_message(
                technical_details,
                email_settings_file=email_settings_file,
            ),
        )
        return {
            "ok": False,
            "message": humanize_smtp_error(error),
            "technical_details": technical_details,
        }

    return {
        "ok": True,
        "message": "Test email sent successfully.",
    }


def contains_sensitive_secret(
    text: str,
    *,
    email_settings_file: Path | str | None = None,
) -> bool:
    if re.search(r"SMTP_PASSWORD\s*[:=]\s*\S+", text, re.IGNORECASE):
        return True
    password = os.getenv("SMTP_PASSWORD", "")
    if password and password in text:
        return True
    return contains_stored_password(text, settings_file=email_settings_file)
