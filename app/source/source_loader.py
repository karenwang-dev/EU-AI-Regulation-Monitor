import json
from pathlib import Path


MONITORS_FILE = Path("config/monitors.json")
SOURCES_FILE = Path("config/sources.json")

ALLOWED_FREQUENCIES = {"daily", "weekly"}

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

    url = monitor["url"]
    if not isinstance(url, str) or not url.strip():
        raise MonitorConfigError(
            f"{label} '{monitor.get('id', '')}': url is required"
        )
    if not url.startswith(("http://", "https://")):
        raise MonitorConfigError(
            f"{label} '{monitor.get('id', '')}': url must start with http:// or https://"
        )

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


def normalize_legacy_source(source: dict) -> dict:
    return {
        "id": source["id"],
        "name": source["name"],
        "url": source["url"],
        "keywords": source.get("keywords", source.get("tags", [])),
        "category": source.get("category", source.get("type", "")),
        "frequency": source.get(
            "frequency",
            source.get("crawl_interval", ""),
        ),
        "enabled": source.get("enabled", True),
    }


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def _validate_monitors(monitors: list[dict]) -> list[dict]:
    validated = []
    for index, monitor in enumerate(monitors):
        normalized = normalize_legacy_source(monitor)
        validate_monitor(normalized, index=index)
        validated.append(normalized)
    return validated


def load_monitors(
    monitors_file: Path = MONITORS_FILE,
    sources_file: Path = SOURCES_FILE,
) -> list[dict]:
    if monitors_file.exists():
        data = _load_json(monitors_file)
        monitors = data.get("monitors", [])
        return _validate_monitors(monitors)

    if sources_file.exists():
        data = _load_json(sources_file)
        legacy_sources = data.get("sources", [])
        return _validate_monitors(legacy_sources)

    raise FileNotFoundError(
        f"No monitor configuration found. Expected {monitors_file} "
        f"or legacy {sources_file}."
    )


def load_sources(
    monitors_file: Path = MONITORS_FILE,
    sources_file: Path = SOURCES_FILE,
) -> list[dict]:
    return load_monitors(
        monitors_file=monitors_file,
        sources_file=sources_file,
    )
