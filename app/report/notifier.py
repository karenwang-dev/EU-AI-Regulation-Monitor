from __future__ import annotations

from pathlib import Path

from app.notification.email_sender import EmailSendError, humanize_smtp_error
from app.notification.notifier import NOTIFICATION_FILE
from app.report.config import load_report_config
from app.report.delivery import resolve_report_delivery_readiness
from app.report.email_sender import send_report_email


def should_send_report_email(report: dict, report_config: dict) -> tuple[bool, str]:
    """Return whether an automatically generated report warrants an email."""
    policy = report_config.get("email_delivery_policy", "high_or_medium")
    summary = report.get("summary") or {}
    total_changes = int(summary.get("total_changes", 0) or 0)
    high_risk = int(summary.get("high_risk", 0) or 0)
    medium_risk = int(summary.get("medium_risk", 0) or 0)

    if policy == "always":
        return True, "Automatic delivery policy: send every weekly report."
    if policy == "changes_only":
        return (
            total_changes > 0,
            "Automatic delivery skipped: no changes were detected."
            if total_changes == 0
            else "Automatic delivery policy: changes were detected.",
        )
    if policy == "high_only":
        return (
            high_risk > 0,
            "Automatic delivery skipped: no high-risk changes were detected."
            if high_risk == 0
            else "Automatic delivery policy: high-risk changes were detected.",
        )
    return (
        high_risk + medium_risk > 0,
        "Automatic delivery skipped: no high- or medium-risk changes were detected."
        if high_risk + medium_risk == 0
        else "Automatic delivery policy: high- or medium-risk changes were detected.",
    )


def _send_with_smtp_config(
    report: dict,
    smtp_config: dict,
    *,
    attachment_path: Path | str | None,
    send_report_email_fn,
) -> dict:
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


def notify_weekly_report(
    report: dict,
    *,
    attachment_path: Path | str | None = None,
    report_config_file: Path | str | None = None,
    notification_file: Path = NOTIFICATION_FILE,
    email_settings_file: Path | str | None = None,
    force: bool = False,
    send_report_email_fn=send_report_email,
) -> dict:
    report_config = load_report_config(report_config_file)
    if not force:
        should_send, reason = should_send_report_email(report, report_config)
        if not should_send:
            return {
                "sent": False,
                "skipped": True,
                "status": "Skipped",
                "reason": reason,
                "delivery_policy": report_config["email_delivery_policy"],
            }

    smtp_config, early_result = resolve_report_delivery_readiness(
        report_config_file=report_config_file,
        notification_file=notification_file,
        email_settings_file=email_settings_file,
    )
    if early_result is not None:
        if early_result.get("status") == "Failed":
            print(f"Weekly report email notification failed: {early_result['reason']}")
        return early_result

    return _send_with_smtp_config(
        report,
        smtp_config,
        attachment_path=attachment_path,
        send_report_email_fn=send_report_email_fn,
    )
