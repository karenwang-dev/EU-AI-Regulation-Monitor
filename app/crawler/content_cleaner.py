from __future__ import annotations

import re


HN_POINTS_PATTERN = re.compile(r"\b\d+\s+points?\b", re.IGNORECASE)
HN_COMMENTS_PATTERN = re.compile(r"\b\d+\s+comments?\b", re.IGNORECASE)
HN_AGE_PATTERN = re.compile(
    r"\b\d+\s+(?:minute|hour|day|month|year)s?\s+ago\b",
    re.IGNORECASE,
)
HN_RANK_PATTERN = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)


def clean_monitor_content(markdown: str, monitor: dict) -> str:
    mode = str(monitor.get("content_normalization_mode", "raw")).strip().lower()
    if mode != "normalized":
        return markdown

    profile = str(monitor.get("content_cleaner_profile", "")).strip().lower()
    if profile == "hacker_news":
        return normalize_hacker_news_content(markdown)
    return markdown


def normalize_hacker_news_content(markdown: str) -> str:
    cleaned = markdown
    cleaned = HN_POINTS_PATTERN.sub("[points]", cleaned)
    cleaned = HN_COMMENTS_PATTERN.sub("[comments]", cleaned)
    cleaned = HN_AGE_PATTERN.sub("[age]", cleaned)
    cleaned = HN_RANK_PATTERN.sub("", cleaned)
    return cleaned
