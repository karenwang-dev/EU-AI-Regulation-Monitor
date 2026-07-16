from __future__ import annotations


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
) -> dict | None:
    extraction = analysis.get("regulation_extraction")
    if not extraction:
        return None

    category = str(extraction.get("category", "")).strip()
    if not category:
        category = str(monitor.get("category", "")).strip()

    return {
        "snapshot_id": snapshot.get("id"),
        "source_id": snapshot.get("source_id") or monitor.get("id", ""),
        "title": str(extraction.get("title", "")).strip(),
        "category": category,
        "regulation_type": str(extraction.get("regulation_type", "")).strip(),
        "summary": str(extraction.get("summary", "")).strip(),
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
