from __future__ import annotations

import re

BUILTIN_CATEGORIES = [
    "eu_regulation",
    "national_regulation",
    "regulatory_guidance",
    "industry_standard",
    "policy_update",
    "news_and_announcement",
    "technical_requirement",
    "other",
]

CATEGORY_VALIDATION_MESSAGE = "Category must contain letters or numbers."


class CategoryValidationError(ValueError):
    pass


def normalize_category(value: str) -> str:
    trimmed = (value or "").strip()
    if not trimmed:
        raise CategoryValidationError(CATEGORY_VALIDATION_MESSAGE)

    normalized = re.sub(r"[\s\-]+", "_", trimmed.lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")

    if not normalized or not re.search(r"[a-z0-9]", normalized):
        raise CategoryValidationError(CATEGORY_VALIDATION_MESSAGE)

    if not re.fullmatch(r"[a-z0-9_]+", normalized):
        raise CategoryValidationError(CATEGORY_VALIDATION_MESSAGE)

    return normalized


def merge_category_options(
    *,
    stored: list[str] | None = None,
    current: str | None = None,
) -> list[str]:
    canonical_by_key: dict[str, str] = {}

    def add(value: str | None) -> None:
        if value is None:
            return
        cleaned = str(value).strip()
        if not cleaned:
            return
        key = cleaned.lower()
        if key not in canonical_by_key:
            canonical_by_key[key] = cleaned

    for category in BUILTIN_CATEGORIES:
        add(category)
    for category in stored or []:
        add(category)
    add(current)

    ordered: list[str] = []
    seen_keys: set[str] = set()
    for category in BUILTIN_CATEGORIES:
        key = category.lower()
        if key in canonical_by_key and key not in seen_keys:
            ordered.append(canonical_by_key[key])
            seen_keys.add(key)

    extras = sorted(
        (value for key, value in canonical_by_key.items() if key not in seen_keys),
        key=str.lower,
    )
    ordered.extend(extras)
    return ordered
