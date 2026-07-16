from __future__ import annotations

import json

from app.knowledge.statistics import fetch_all_knowledge_items
from app.storage.service import StorageService

VALID_IMPACT_LEVELS = {"HIGH", "MEDIUM", "LOW", "NONE"}
IMPACT_SORT_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NONE": 3}


def _lookup_analysis_for_snapshot(
    storage: StorageService,
    snapshot_id: int | None,
) -> dict | None:
    if snapshot_id is None:
        return None

    with storage._connect() as connection:
        row = connection.execute(
            """
            SELECT analysis_json
            FROM analyses
            WHERE snapshot_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (snapshot_id,),
        ).fetchone()

    if row is None:
        return None

    return json.loads(row["analysis_json"])


def _display_value(value) -> str:
    if value is None:
        return "N/A"
    cleaned = str(value).strip()
    return cleaned or "N/A"


def _normalize_string_list(values) -> list[str]:
    if not values:
        return []
    return [
        str(value).strip()
        for value in values
        if str(value).strip()
    ]


def _normalize_impact_level(value) -> str:
    normalized = str(value or "NONE").strip().upper()
    if normalized not in VALID_IMPACT_LEVELS:
        return "NONE"
    return normalized


def build_compliance_insight(
    item: dict,
    storage: StorageService,
) -> dict:
    analysis = _lookup_analysis_for_snapshot(
        storage,
        item.get("snapshot_id"),
    ) or {}
    extraction = analysis.get("regulation_extraction") or {}

    impact_level = _normalize_impact_level(analysis.get("impact_level"))
    affected_modules = _normalize_string_list(
        item.get("modules") or analysis.get("affected_modules")
    )
    recommended_actions = _normalize_string_list(
        item.get("actions") or analysis.get("recommended_actions")
    )

    publish_date = extraction.get("publish_date") or item.get("publish_date")
    effective_date = item.get("effective_date") or extraction.get("effective_date")

    return {
        "id": item.get("id"),
        "title": _display_value(item.get("title")),
        "category": _display_value(item.get("category")),
        "impact_level": impact_level,
        "affected_modules": affected_modules,
        "recommended_actions": recommended_actions,
        "publish_date": _display_value(publish_date),
        "effective_date": _display_value(effective_date),
        "detail_url": f"/knowledge/{item.get('id')}",
        "summary": str(item.get("summary", "")).strip(),
    }


def build_compliance_insights(storage: StorageService) -> list[dict]:
    items = fetch_all_knowledge_items(storage)
    insights = [
        build_compliance_insight(item, storage)
        for item in items
    ]
    insights.sort(
        key=lambda insight: (
            IMPACT_SORT_ORDER.get(insight["impact_level"], 99),
            insight["title"],
        )
    )
    return insights


def filter_compliance_insights(
    insights: list[dict],
    *,
    query: str = "",
    category: str = "",
    module: str = "",
    impact: str = "",
) -> list[dict]:
    filtered = insights

    if query.strip():
        needle = query.strip().lower()
        filtered = [
            insight
            for insight in filtered
            if needle in insight["title"].lower()
            or needle in insight["category"].lower()
            or needle in insight.get("summary", "").lower()
            or needle in " ".join(insight["affected_modules"]).lower()
            or needle in " ".join(insight["recommended_actions"]).lower()
        ]

    if category.strip():
        category_value = category.strip()
        filtered = [
            insight
            for insight in filtered
            if insight["category"] == category_value
        ]

    if module.strip():
        module_value = module.strip().lower()
        filtered = [
            insight
            for insight in filtered
            if any(
                module_value == affected_module.lower()
                for affected_module in insight["affected_modules"]
            )
        ]

    if impact.strip():
        impact_value = impact.strip().upper()
        filtered = [
            insight
            for insight in filtered
            if insight["impact_level"] == impact_value
        ]

    return filtered


def build_insight_summary(insights: list[dict]) -> dict:
    return {
        "high_priority": sum(
            1 for insight in insights if insight["impact_level"] == "HIGH"
        ),
        "medium_priority": sum(
            1 for insight in insights if insight["impact_level"] == "MEDIUM"
        ),
        "low_priority": sum(
            1 for insight in insights if insight["impact_level"] == "LOW"
        ),
        "total_regulations": len(insights),
    }


def get_insight_filter_options(
    insights: list[dict],
) -> tuple[list[str], list[str]]:
    categories = sorted(
        {
            insight["category"]
            for insight in insights
            if insight["category"] != "N/A"
        }
    )
    modules = sorted(
        {
            module
            for insight in insights
            for module in insight["affected_modules"]
            if str(module).strip()
        }
    )
    return categories, modules
