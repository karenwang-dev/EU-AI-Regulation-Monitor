from __future__ import annotations

IMPACT_ALIASES = {
    "HIGH": "HIGH",
    "MEDIUM": "MEDIUM",
    "LOW": "LOW",
    "NONE": "NONE",
}


def normalize_impact(value) -> str:
    normalized = str(value or "").strip().upper()
    if not normalized:
        return "NONE"
    return IMPACT_ALIASES.get(normalized, "UNKNOWN")


def get_change_impact(change: dict) -> str:
    analysis = change.get("analysis")
    if isinstance(analysis, dict):
        for key in ("impact_level", "impact"):
            value = analysis.get(key)
            if value is not None and str(value).strip():
                return str(value)

    for key in ("impact_level", "impact"):
        value = change.get(key)
        if value is not None and str(value).strip():
            return str(value)

    return ""


def normalized_change_impact(change: dict) -> str:
    return normalize_impact(get_change_impact(change))


def is_displayable_change(change: dict) -> bool:
    diff_id = change.get("diff_id")
    return diff_id is not None and str(diff_id).strip() != ""


def count_changes_by_impact(changes: list[dict]) -> dict[str, int]:
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for change in changes:
        if not is_displayable_change(change):
            continue
        level = normalized_change_impact(change)
        if level in counts:
            counts[level] += 1
    return counts


def filter_changes_by_impact(
    changes: list[dict],
    impact: str,
) -> list[dict]:
    impact_value = normalize_impact(impact)
    return [
        change
        for change in changes
        if normalized_change_impact(change) == impact_value
    ]
