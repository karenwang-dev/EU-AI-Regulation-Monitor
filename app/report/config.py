from __future__ import annotations

import json
from pathlib import Path

REPORT_CONFIG_FILE = Path("config/report.json")

DEFAULT_REPORT_CONFIG = {
    "enabled": True,
    "frequency": "weekly",
    "day": "mon",
    "hour": 8,
    "minute": 30,
    "email_enabled": False,
    # Send routine reports only when they need attention.  Operators can still
    # send any saved report manually from the Reports page.
    "email_delivery_policy": "high_or_medium",
    "recipients": [],
}

EMAIL_DELIVERY_POLICIES = {
    "always",
    "changes_only",
    "high_or_medium",
    "high_only",
}

EMAIL_DELIVERY_POLICY_LABELS = {
    "always": "Send every weekly report",
    "changes_only": "Send when any change is detected",
    "high_or_medium": "Send for high- or medium-risk changes",
    "high_only": "Send for high-risk changes only",
}


def email_delivery_policy_label(policy: str) -> str:
    return EMAIL_DELIVERY_POLICY_LABELS.get(
        policy,
        EMAIL_DELIVERY_POLICY_LABELS["high_or_medium"],
    )

DAY_ALIASES = {
    "mon": "mon",
    "monday": "mon",
    "tue": "tue",
    "tuesday": "tue",
    "wed": "wed",
    "wednesday": "wed",
    "thu": "thu",
    "thursday": "thu",
    "fri": "fri",
    "friday": "fri",
    "sat": "sat",
    "saturday": "sat",
    "sun": "sun",
    "sunday": "sun",
}


def normalize_report_config(config: dict) -> dict:
    day = str(config.get("day", "mon")).strip().lower()
    config["day"] = DAY_ALIASES.get(day, "mon")

    try:
        config["hour"] = int(config.get("hour", 8))
    except (TypeError, ValueError):
        config["hour"] = 8

    try:
        config["minute"] = int(config.get("minute", 30))
    except (TypeError, ValueError):
        config["minute"] = 30

    config["hour"] = max(0, min(config["hour"], 23))
    config["minute"] = max(0, min(config["minute"], 59))
    config["enabled"] = bool(config.get("enabled", True))
    config["frequency"] = str(config.get("frequency", "weekly")).strip().lower()
    config["email_enabled"] = bool(config.get("email_enabled", False))
    delivery_policy = str(
        config.get("email_delivery_policy", "high_or_medium")
    ).strip().lower()
    config["email_delivery_policy"] = (
        delivery_policy
        if delivery_policy in EMAIL_DELIVERY_POLICIES
        else "high_or_medium"
    )
    config["recipients"] = [
        str(recipient).strip()
        for recipient in config.get("recipients", [])
        if str(recipient).strip()
    ]
    return config


def load_report_config(
    config_file: Path | str | None = None,
) -> dict:
    path = Path(config_file) if config_file is not None else REPORT_CONFIG_FILE
    if not path.exists():
        return DEFAULT_REPORT_CONFIG.copy()

    with open(path, "r", encoding="utf-8") as file:
        raw_config = json.load(file)

    if not isinstance(raw_config, dict):
        return DEFAULT_REPORT_CONFIG.copy()

    config = DEFAULT_REPORT_CONFIG.copy()
    config.update(raw_config)
    return normalize_report_config(config)
