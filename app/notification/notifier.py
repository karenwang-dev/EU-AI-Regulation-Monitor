import json
from pathlib import Path

from app.notification.email_sender import EmailSendError, send_email


NOTIFICATION_FILE = Path("config/notification.json")
NOTIFIABLE_IMPACT_LEVELS = {"HIGH", "MEDIUM"}


class NotificationConfigError(ValueError):
    pass


def _validate_notification_config(config: dict) -> dict:
    if not isinstance(config, dict):
        raise NotificationConfigError("Notification config must be a JSON object.")

    required_fields = (
        "enabled",
        "from_address",
        "to_addresses",
        "smtp_host",
        "smtp_port",
    )
    for field in required_fields:
        if field not in config:
            raise NotificationConfigError(
                f"Missing required notification field: {field}"
            )

    if not isinstance(config["to_addresses"], list) or not config["to_addresses"]:
        raise NotificationConfigError(
            "to_addresses must be a non-empty list."
        )

    return config


def load_notification_config(
    notification_file: Path = NOTIFICATION_FILE,
) -> dict:
    if not notification_file.exists():
        raise NotificationConfigError(
            f"Notification config not found: {notification_file}"
        )

    with open(notification_file, "r", encoding="utf-8") as file:
        config = json.load(file)

    return _validate_notification_config(config)


def should_notify(analysis: dict) -> bool:
    impact_level = str(analysis.get("impact_level", "NONE")).upper()
    return impact_level in NOTIFIABLE_IMPACT_LEVELS


def build_email_content(
    monitor: dict,
    analysis: dict,
    snapshot_id: int,
) -> tuple[str, str]:
    impact_level = str(analysis.get("impact_level", "NONE")).upper()
    subject_prefix = "[AI Regulation Monitor]"
    subject = (
        f"{subject_prefix} {impact_level} impact detected: "
        f"{monitor.get('name', monitor.get('id', 'Unknown'))}"
    )

    affected_modules = analysis.get("affected_modules", [])
    recommended_actions = analysis.get("recommended_actions", [])

    body_lines = [
        "AI Regulation Monitoring Alert",
        "",
        f"Monitor: {monitor.get('name', '')}",
        f"Monitor ID: {monitor.get('id', '')}",
        f"Category: {monitor.get('category', '')}",
        f"URL: {monitor.get('url', '')}",
        f"Snapshot ID: {snapshot_id}",
        "",
        f"Impact Level: {impact_level}",
        f"Confidence: {analysis.get('confidence', '')}",
        f"Reason: {analysis.get('reason', '')}",
        "",
        "Affected Modules:",
    ]

    if affected_modules:
        body_lines.extend(f"- {module}" for module in affected_modules)
    else:
        body_lines.append("- None")

    body_lines.extend(["", "Recommended Actions:"])
    if recommended_actions:
        body_lines.extend(f"- {action}" for action in recommended_actions)
    else:
        body_lines.append("- None")

    return subject, "\n".join(body_lines)


def notify_if_needed(
    monitor: dict,
    analysis: dict,
    snapshot_id: int,
    notification_file: Path = NOTIFICATION_FILE,
    send_email_fn=send_email,
) -> dict:
    try:
        config = load_notification_config(notification_file)
    except (NotificationConfigError, json.JSONDecodeError) as error:
        return {
            "sent": False,
            "skipped": True,
            "reason": f"Invalid notification config: {error}",
        }

    if not config.get("enabled", False):
        return {
            "sent": False,
            "skipped": True,
            "reason": "Notifications are disabled.",
        }

    if not should_notify(analysis):
        return {
            "sent": False,
            "skipped": True,
            "reason": (
                f"Impact level {analysis.get('impact_level', 'NONE')} "
                "does not require notification."
            ),
        }

    subject, body = build_email_content(monitor, analysis, snapshot_id)
    subject_prefix = config.get("subject_prefix")
    if subject_prefix:
        subject = subject.replace("[AI Regulation Monitor]", subject_prefix)

    try:
        send_email_fn(config, subject, body)
    except EmailSendError as error:
        return {
            "sent": False,
            "skipped": False,
            "reason": f"Email send failed: {error}",
        }

    return {
        "sent": True,
        "skipped": False,
        "reason": "Notification email sent.",
        "subject": subject,
    }
