from __future__ import annotations

from app.storage.service import StorageService

RELATION_BADGE_CLASSES = {
    "AMENDMENT": "text-bg-danger",
    "GUIDANCE": "text-bg-warning text-dark",
    "IMPLEMENTATION": "text-bg-primary",
    "RELATED": "text-bg-success",
    "REPLACED_BY": "text-bg-dark",
    "SUPERSEDES": "badge-relation-supersedes",
}


def get_relation_badge_class(relation: str) -> str:
    normalized = str(relation or "").strip().upper()
    return RELATION_BADGE_CLASSES.get(normalized, "text-bg-secondary")


def format_confidence_percent(confidence: float | int | str) -> int:
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        return 0
    return int(round(value * 100))


def resolve_related_regulations(
    item: dict,
    storage: StorageService,
) -> list[dict]:
    relationships = item.get("relationships") or []
    if not isinstance(relationships, list):
        return []

    related_regulations: list[dict] = []
    for relationship in relationships:
        if not isinstance(relationship, dict):
            continue

        knowledge_id = relationship.get("knowledge_id")
        if knowledge_id is None:
            continue

        try:
            resolved_id = int(knowledge_id)
        except (TypeError, ValueError):
            continue

        related_item = storage.get_knowledge_item(resolved_id)
        if related_item is None:
            continue

        relation = str(relationship.get("relation", "RELATED")).strip().upper()
        try:
            confidence = float(relationship.get("confidence", 0))
        except (TypeError, ValueError):
            confidence = 0.0

        confidence_percent = format_confidence_percent(confidence)
        related_regulations.append(
            {
                "knowledge_id": resolved_id,
                "title": str(related_item.get("title", "")).strip() or "N/A",
                "relation": relation,
                "confidence": confidence,
                "confidence_percent": confidence_percent,
                "reason": str(relationship.get("reason", "")).strip(),
                "badge_class": get_relation_badge_class(relation),
                "detail_url": f"/knowledge/{resolved_id}",
            }
        )

    return related_regulations
