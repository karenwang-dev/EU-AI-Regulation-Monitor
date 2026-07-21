from __future__ import annotations

import re
from urllib.parse import urlparse


def _compile_patterns(patterns: list[str]) -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []
    for pattern in patterns:
        cleaned = str(pattern or "").strip()
        if cleaned:
            compiled.append(re.compile(cleaned))
    return compiled


def url_matches_any_pattern(url: str, patterns: list[str]) -> bool:
    compiled = _compile_patterns(patterns)
    if not compiled:
        return True
    return any(pattern.search(url) for pattern in compiled)


def url_matches_exclude_patterns(url: str, patterns: list[str]) -> bool:
    if not patterns:
        return False

    parsed = urlparse(url)
    haystack = f"{parsed.path}?{parsed.query}"
    for fragment in patterns:
        token = str(fragment or "").strip()
        if token and token in haystack:
            return True
    return False


def is_url_allowed_for_monitor(url: str, monitor: dict) -> bool:
    include_patterns = monitor.get("include_patterns") or []
    exclude_patterns = monitor.get("exclude_patterns") or []

    if exclude_patterns and url_matches_exclude_patterns(url, exclude_patterns):
        return False

    if include_patterns:
        return url_matches_any_pattern(url, include_patterns)

    return True
