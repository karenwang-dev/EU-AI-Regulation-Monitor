from __future__ import annotations

import re


class MonitorUrlValidationError(ValueError):
    pass

MARKDOWN_LINK_PATTERN = re.compile(r"^\[([^\]]+)\]\(([^)]+)\)$")


def normalize_monitor_url(url: str) -> str:
    cleaned = str(url or "").strip()
    if not cleaned:
        return cleaned

    match = MARKDOWN_LINK_PATTERN.match(cleaned)
    if match:
        cleaned = match.group(2).strip()

    return cleaned


def validate_monitor_url(url: str, *, label: str = "monitor") -> str:
    cleaned = normalize_monitor_url(url)
    if not cleaned:
        raise MonitorUrlValidationError(f"{label}: url is required")
    if not cleaned.startswith(("http://", "https://")):
        raise MonitorUrlValidationError(
            f"{label}: url must start with http:// or https://"
        )
    return cleaned
