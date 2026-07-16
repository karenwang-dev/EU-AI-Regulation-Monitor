from __future__ import annotations

from app.knowledge.relationship import build_relationships


def _normalize_string_list(values) -> list[str]:
    if not values:
        return []
    return [
        str(value).strip()
        for value in values
        if str(value).strip()
    ]


def build_knowledge_item(
    snapshot: dict,
    monitor: dict,
    analysis: dict,
    existing_items: list[dict] | None = None,
) -> dict | None:
    extraction = analysis.get("regulation_extraction")
    if not extraction:
        return None

    category = str(extraction.get("category", "")).strip()
    if not category:
        category = str(monitor.get("category", "")).strip()

    item = {
        "snapshot_id": snapshot.get("id"),
        "source_id": snapshot.get("source_id") or monitor.get("id", ""),
        "title": str(extraction.get("title", "")).strip(),
        "category": category,
        "regulation_type": str(extraction.get("regulation_type", "")).strip(),
        "summary": str(extraction.get("summary", "")).strip(),
        "publish_date": str(extraction.get("publish_date", "")).strip(),
        "effective_date": str(extraction.get("effective_date", "")).strip(),
        "countries": _normalize_string_list(
            extraction.get("affected_countries", [])
        ),
        "products": _normalize_string_list(
            extraction.get("affected_products", [])
        ),
        "modules": _normalize_string_list(
            extraction.get("affected_modules", [])
        ),
        "requirements": _normalize_string_list(
            extraction.get("key_requirements", [])
        ),
        "actions": _normalize_string_list(
            extraction.get("actions_required", [])
        ),
        "confidence": str(extraction.get("confidence", "")).strip(),
    }

    if existing_items:
        item["relationships"] = build_relationships(item, existing_items)
    else:
        item["relationships"] = []

    return item
