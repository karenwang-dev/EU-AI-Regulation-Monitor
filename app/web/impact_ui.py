from __future__ import annotations

from app.web.change_helper import normalize_impact

IMPACT_UI = {
    "HIGH": {
        "text_class": "text-danger",
        "border_class": "border-danger",
        "badge_class": "text-bg-danger",
        "background_class": "bg-danger-subtle",
    },
    "MEDIUM": {
        "text_class": "text-warning-emphasis",
        "border_class": "border-warning",
        "badge_class": "text-bg-warning",
        "background_class": "bg-warning-subtle",
    },
    "LOW": {
        "text_class": "text-success",
        "border_class": "border-success",
        "badge_class": "text-bg-success",
        "background_class": "bg-success-subtle",
    },
}

NEUTRAL_UI = {
    "border_class": "border-secondary",
    "label_class": "text-secondary",
    "count_class": "text-secondary",
    "background_class": "",
}


def get_impact_ui(level: str) -> dict:
    return IMPACT_UI.get(normalize_impact(level), {})


def get_dashboard_risk_card_classes(level: str, count: int) -> dict:
    if count <= 0:
        return dict(NEUTRAL_UI)

    ui = get_impact_ui(level)
    if not ui:
        return dict(NEUTRAL_UI)

    return {
        "border_class": ui["border_class"],
        "label_class": ui["text_class"],
        "count_class": ui["text_class"],
        "background_class": ui["background_class"],
    }


def get_impact_badge_classes(level: str) -> str:
    normalized = normalize_impact(level)
    ui = IMPACT_UI.get(normalized)
    if not ui:
        return "badge rounded-pill text-bg-secondary"

    badge_class = ui["badge_class"]
    if normalized == "MEDIUM":
        return f"badge rounded-pill {badge_class} text-dark"
    return f"badge rounded-pill {badge_class}"
