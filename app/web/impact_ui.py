from __future__ import annotations

from app.web.change_helper import normalize_impact

IMPACT_UI = {
    "HIGH": {
        "badge_class": "text-bg-danger",
        "risk_class": "risk-high",
    },
    "MEDIUM": {
        "badge_class": "text-bg-warning",
        "risk_class": "risk-medium",
    },
    "LOW": {
        "badge_class": "text-bg-success",
        "risk_class": "risk-low",
    },
}

NEUTRAL_RISK_CLASS = "risk-neutral"


def get_impact_ui(level: str) -> dict:
    return IMPACT_UI.get(normalize_impact(level), {})


def get_dashboard_risk_card_classes(level: str, count: int) -> dict:
    if count <= 0:
        return {"risk_class": NEUTRAL_RISK_CLASS}

    ui = get_impact_ui(level)
    if not ui:
        return {"risk_class": NEUTRAL_RISK_CLASS}

    return {"risk_class": ui["risk_class"]}


def get_impact_badge_classes(level: str) -> str:
    normalized = normalize_impact(level)
    ui = IMPACT_UI.get(normalized)
    if not ui:
        return "badge rounded-pill text-bg-secondary"

    badge_class = ui["badge_class"]
    if normalized == "MEDIUM":
        return f"badge rounded-pill {badge_class} text-dark"
    return f"badge rounded-pill {badge_class}"
