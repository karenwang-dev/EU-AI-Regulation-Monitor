from pathlib import Path

from app.crawler.url_validation import (
    MonitorUrlValidationError,
    validate_monitor_url,
)

MONITORS_FILE = Path("config/monitors.json")
SOURCES_FILE = Path("config/sources.json")

ALLOWED_FREQUENCIES = {"daily", "weekly"}
ALLOWED_CRAWL_MODES = {"single", "smart", "multi_page"}
DEFAULT_CRAWL_MODE = "single"
DEFAULT_MAX_DEPTH = 0
DEFAULT_MAX_PAGES = 1
OPTIONAL_LIST_FIELDS = (
    "include_patterns",
    "exclude_patterns",
    "seed_paths",
)

REQUIRED_MONITOR_FIELDS = (
    "id",
    "name",
    "url",
    "keywords",
    "category",
    "frequency",
)


class MonitorConfigError(ValueError):
    pass


def validate_monitor(monitor: dict, index: int | None = None) -> None:
    label = f"monitor[{index}]" if index is not None else "monitor"

    for field in REQUIRED_MONITOR_FIELDS:
        if field not in monitor:
            raise MonitorConfigError(
                f"{label}: missing required field '{field}'"
            )

    monitor_id = monitor.get("id", "")
    try:
        validate_monitor_url(
            monitor.get("url", ""),
            label=f"{label} '{monitor_id}'",
        )
    except MonitorUrlValidationError as error:
        raise MonitorConfigError(str(error)) from error

    keywords = monitor["keywords"]
    if not isinstance(keywords, list) or not keywords:
        raise MonitorConfigError(
            f"{label} '{monitor.get('id', '')}': keywords must be a non-empty list"
        )
    if not all(isinstance(keyword, str) and keyword.strip() for keyword in keywords):
        raise MonitorConfigError(
            f"{label} '{monitor.get('id', '')}': keywords must contain non-empty strings"
        )

    frequency = monitor["frequency"]
    if frequency not in ALLOWED_FREQUENCIES:
        allowed = ", ".join(sorted(ALLOWED_FREQUENCIES))
        raise MonitorConfigError(
            f"{label} '{monitor.get('id', '')}': frequency must be one of: {allowed}"
        )

    crawl_mode = monitor.get("crawl_mode", DEFAULT_CRAWL_MODE)
    if crawl_mode not in ALLOWED_CRAWL_MODES:
        allowed = ", ".join(sorted(ALLOWED_CRAWL_MODES))
        raise MonitorConfigError(
            f"{label} '{monitor.get('id', '')}': crawl_mode must be one of: {allowed}"
        )

    max_depth = monitor.get("max_depth", DEFAULT_MAX_DEPTH)
    if not isinstance(max_depth, int) or isinstance(max_depth, bool):
        raise MonitorConfigError(
            f"{label} '{monitor.get('id', '')}': max_depth must be an integer"
        )
    if max_depth < 0:
        raise MonitorConfigError(
            f"{label} '{monitor.get('id', '')}': max_depth must be >= 0"
        )

    max_pages = monitor.get("max_pages", DEFAULT_MAX_PAGES)
    if not isinstance(max_pages, int) or isinstance(max_pages, bool):
        raise MonitorConfigError(
            f"{label} '{monitor.get('id', '')}': max_pages must be an integer"
        )
    if max_pages <= 0:
        raise MonitorConfigError(
            f"{label} '{monitor.get('id', '')}': max_pages must be > 0"
        )

    for field in OPTIONAL_LIST_FIELDS:
        if field not in monitor:
            continue
        value = monitor[field]
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            raise MonitorConfigError(
                f"{label} '{monitor.get('id', '')}': {field} must be a list of strings"
            )

    content_mode = monitor.get("content_normalization_mode", "raw")
    if content_mode not in {"raw", "normalized"}:
        raise MonitorConfigError(
            f"{label} '{monitor.get('id', '')}': content_normalization_mode must be raw or normalized"
        )

    fetch_mode = monitor.get("fetch_mode")
    if fetch_mode is not None and str(fetch_mode).strip().lower() not in {"firecrawl", "http"}:
        raise MonitorConfigError(
            f"{label} '{monitor.get('id', '')}': fetch_mode must be firecrawl or http"
        )

    from app.monitors.smart_discovery import validate_smart_discovery_config

    for message in validate_smart_discovery_config(monitor):
        raise MonitorConfigError(f"{label} '{monitor.get('id', '')}': {message}")


def normalize_legacy_source(source: dict) -> dict:
    from app.crawler.url_validation import normalize_monitor_url

    return {
        "id": source["id"],
        "name": source["name"],
        "url": normalize_monitor_url(source.get("url", "")),
        "keywords": source.get("keywords", source.get("tags", [])),
        "category": source.get("category", source.get("type", "")),
        "frequency": source.get(
            "frequency",
            source.get("crawl_interval", ""),
        ),
        "enabled": source.get("enabled", True),
        "crawl_mode": source.get("crawl_mode", DEFAULT_CRAWL_MODE),
        "max_depth": source.get("max_depth", DEFAULT_MAX_DEPTH),
        "max_pages": source.get("max_pages", DEFAULT_MAX_PAGES),
        "include_patterns": source.get("include_patterns", []),
        "exclude_patterns": source.get("exclude_patterns", []),
        "seed_paths": source.get("seed_paths", []),
        "same_domain_only": source.get("same_domain_only", True),
        "fetch_mode": source.get("fetch_mode"),
        "skip_ai_analysis": source.get("skip_ai_analysis", False),
        "content_normalization_mode": source.get(
            "content_normalization_mode",
            "raw",
        ),
        "content_cleaner_profile": source.get("content_cleaner_profile"),
        "description": source.get("description", ""),
    }


def load_monitors(
    repository=None,
    monitors_file: Path | None = None,
    sources_file: Path | None = None,
) -> list[dict]:
    from app.monitors.repository import get_monitor_repository

    if repository is not None:
        return repository.list_all()

    if monitors_file is not None or sources_file is not None:
        repo = get_monitor_repository(
            seed_file=monitors_file,
            sources_file=sources_file,
        )
        return repo.list_all()

    return get_monitor_repository().list_all()


def load_sources(
    repository=None,
    monitors_file: Path | None = None,
    sources_file: Path | None = None,
) -> list[dict]:
    return load_monitors(
        repository=repository,
        monitors_file=monitors_file,
        sources_file=sources_file,
    )
