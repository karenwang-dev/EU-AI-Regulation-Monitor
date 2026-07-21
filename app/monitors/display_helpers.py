from __future__ import annotations

import re


def format_category_label(category: str | None) -> str:
    if not category:
        return "Other"
    if " " in category and "_" not in category:
        return category
    words = re.sub(r"[_-]+", " ", category.strip()).split()
    return " ".join(word.capitalize() for word in words if word)


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
