from __future__ import annotations

import re

CATEGORY_ACRONYMS = frozenset({"eu", "ai", "dsa", "dma", "gdpr", "uk", "us"})


def _format_category_word(word: str) -> str:
    lower = word.lower()
    if lower in CATEGORY_ACRONYMS:
        return lower.upper()
    return word.capitalize()


def format_category_label(category: str | None) -> str:
    if not category:
        return "Other"
    cleaned = category.strip()
    if not cleaned:
        return "Other"
    if " " in cleaned and "_" not in cleaned:
        words = cleaned.split()
        return " ".join(_format_category_word(word) for word in words if word)
    words = re.sub(r"[_-]+", " ", cleaned).split()
    return " ".join(_format_category_word(word) for word in words if word)


def change_status_badge_class(change_status: str | None) -> str:
    mapping = {
        "changed": "text-bg-primary",
        "unchanged": "text-bg-secondary",
        "failed": "text-bg-danger",
        "baseline": "text-bg-info",
        "running": "text-bg-warning text-dark",
    }
    return mapping.get(str(change_status or "").lower(), "text-bg-light text-dark")


def execution_status_badge_class(execution_status: str | None) -> str:
    mapping = {
        "success": "text-bg-success",
        "failed": "text-bg-danger",
        "running": "text-bg-warning text-dark",
    }
    return mapping.get(str(execution_status or "").lower(), "text-bg-secondary")


def format_change_status_label(change_status: str | None) -> str:
    if not change_status:
        return "—"
    return change_status.replace("_", " ").title()


def format_execution_status_label(execution_status: str | None) -> str:
    if not execution_status:
        return "—"
    return execution_status.replace("_", " ").title()
