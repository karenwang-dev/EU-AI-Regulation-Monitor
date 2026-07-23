from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
DEFAULT_APP_TIMEZONE = "Europe/Berlin"


def get_app_timezone() -> ZoneInfo:
    name = os.getenv("APP_TIMEZONE", DEFAULT_APP_TIMEZONE).strip() or DEFAULT_APP_TIMEZONE
    return ZoneInfo(name)


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_now_iso(*, timespec: str = "seconds") -> str:
    return utc_now().isoformat(timespec=timespec)


def parse_legacy_timestamp_as_utc(value: str) -> datetime:
    """Parse a stored timestamp; naive values are assumed UTC (legacy Docker writes)."""
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Timestamp cannot be empty")

    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"

    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
    cleaned = str(value).strip()
    if not cleaned:
        return None
    return parse_legacy_timestamp_as_utc(cleaned)


def normalize_to_utc(value: str | datetime | None) -> datetime | None:
    return parse_datetime(value)


def format_utc_iso(value: str | datetime | None) -> str | None:
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    return parsed.isoformat(timespec="seconds")


def utc_today_prefix() -> str:
    return utc_now().strftime("%Y-%m-%d")
