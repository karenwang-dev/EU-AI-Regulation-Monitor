from __future__ import annotations

from app.crawler.discovery_constants import (
    MIN_SMART_MAX_DEPTH,
    MIN_SMART_MAX_PAGES,
)


def validate_smart_discovery_config(source: dict) -> list[str]:
    if source.get("crawl_mode") != "smart":
        return []

    errors: list[str] = []
    max_depth = int(source.get("max_depth", 0))
    max_pages = int(source.get("max_pages", 1))

    if max_depth < MIN_SMART_MAX_DEPTH:
        errors.append("Smart Discovery requires max_depth >= 1.")
    if max_pages < MIN_SMART_MAX_PAGES:
        errors.append(
            "Smart Discovery requires max_pages >= 2 (homepage counts as one monitored page)."
        )
    return errors
