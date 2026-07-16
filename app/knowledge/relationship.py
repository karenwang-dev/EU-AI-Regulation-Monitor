from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.knowledge.similarity import _list_similarity, _text_similarity

VALID_RELATIONS = {
    "AMENDMENT",
    "GUIDANCE",
    "IMPLEMENTATION",
    "RELATED",
    "REPLACED_BY",
    "SUPERSEDES",
}


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", str(title).strip().lower())


def _title_similarity(left: str, right: str) -> float:
    return _text_similarity(left, right)


def _normalize_regulation_type(value: str) -> str:
    return str(value).strip().upper()


def _parse_date(value: str | None) -> str | None:
    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    if "T" in cleaned:
        return cleaned.split("T", 1)[0]
    if len(cleaned) >= 10:
        return cleaned[:10]
    return cleaned


def _item_reference_date(item: dict) -> str | None:
    for field in ("publish_date", "effective_date", "created_at"):
        parsed = _parse_date(item.get(field))
        if parsed:
            return parsed
    return None


def _is_later(left_date: str | None, right_date: str | None) -> bool:
    if not left_date or not right_date:
        return False
    return left_date > right_date


def _shared_values(left: list, right: list) -> list[str]:
    left_values = {_normalize_title(value) for value in left if str(value).strip()}
    right_values = {
        _normalize_title(value) for value in right if str(value).strip()
    }
    return sorted(left_values & right_values)


def _candidate_relations(
    current: dict,
    other: dict,
) -> list[dict]:
    candidates: list[dict] = []

    title_score = _title_similarity(
        current.get("title", ""),
        other.get("title", ""),
    )
    same_category = (
        _normalize_title(current.get("category", ""))
        == _normalize_title(other.get("category", ""))
        and bool(current.get("category"))
    )
    shared_modules = _shared_values(
        current.get("modules", []),
        other.get("modules", []),
    )
    shared_products = _shared_values(
        current.get("products", []),
        other.get("products", []),
    )
    shared_countries = _shared_values(
        current.get("countries", []),
        other.get("countries", []),
    )

    current_type = _normalize_regulation_type(current.get("regulation_type", ""))
    other_type = _normalize_regulation_type(other.get("regulation_type", ""))
    current_date = _item_reference_date(current)
    other_date = _item_reference_date(other)

    overlap_signals = int(bool(shared_modules)) + int(bool(shared_products)) + int(
        bool(shared_countries)
    )

    if (
        title_score >= 0.7
        and same_category
        and current_type == "AMENDMENT"
        and _is_later(current_date, other_date)
    ):
        candidates.append(
            {
                "relation": "AMENDMENT",
                "confidence": round(
                    min(0.98, 0.75 + (title_score * 0.2)),
                    2,
                ),
                "reason": "Same regulation title with later publish date",
            }
        )

    if (
        title_score >= 0.6
        and (current_type == "GUIDANCE" or other_type == "GUIDANCE")
        and (same_category or shared_modules)
    ):
        candidates.append(
            {
                "relation": "GUIDANCE",
                "confidence": round(
                    min(0.95, 0.65 + (title_score * 0.25)),
                    2,
                ),
                "reason": "Guidance document linked to related regulation scope",
            }
        )

    if (
        title_score >= 0.55
        and current_type in {"NEW", "AMENDMENT"}
        and other_type in {"GUIDANCE", "NEW"}
        and (shared_products or shared_modules)
    ):
        candidates.append(
            {
                "relation": "IMPLEMENTATION",
                "confidence": round(
                    min(0.92, 0.6 + (overlap_signals * 0.1) + (title_score * 0.15)),
                    2,
                ),
                "reason": "Implementation rule aligned with related product scope",
            }
        )

    if (
        title_score >= 0.65
        and _is_later(current_date, other_date)
        and current_type in {"NEW", "AMENDMENT", "OTHER"}
    ):
        candidates.append(
            {
                "relation": "SUPERSEDES",
                "confidence": round(
                    min(0.94, 0.68 + (title_score * 0.2)),
                    2,
                ),
                "reason": "Later regulation version supersedes earlier record",
            }
        )

    if (
        title_score >= 0.65
        and _is_later(other_date, current_date)
        and other_type in {"NEW", "AMENDMENT", "OTHER"}
    ):
        candidates.append(
            {
                "relation": "REPLACED_BY",
                "confidence": round(
                    min(0.94, 0.68 + (title_score * 0.2)),
                    2,
                ),
                "reason": "Earlier regulation replaced by later related record",
            }
        )

    if (
        title_score >= 0.5
        or same_category
        or shared_modules
        or shared_products
        or shared_countries
    ):
        confidence = 0.45
        confidence += title_score * 0.25
        confidence += 0.1 if same_category else 0.0
        confidence += 0.08 * len(shared_modules)
        confidence += 0.05 * len(shared_products)
        confidence += 0.05 * len(shared_countries)
        candidates.append(
            {
                "relation": "RELATED",
                "confidence": round(min(0.9, confidence), 2),
                "reason": "Shared regulation metadata across title, scope, or category",
            }
        )

    return candidates


def build_relationships(
    knowledge_item: dict,
    existing_items: list[dict],
) -> list[dict]:
    current_id = knowledge_item.get("id")
    relationships: list[dict] = []

    for other in existing_items:
        other_id = other.get("id")
        if other_id is None or other_id == current_id:
            continue

        candidates = _candidate_relations(knowledge_item, other)
        if not candidates:
            continue

        specific_candidates = [
            candidate
            for candidate in candidates
            if candidate["relation"] != "RELATED"
            and candidate["confidence"] >= 0.5
        ]
        pool = specific_candidates or candidates
        best = max(pool, key=lambda item: item["confidence"])
        if best["confidence"] < 0.5:
            continue

        relationships.append(
            {
                "knowledge_id": other_id,
                "relation": best["relation"],
                "confidence": best["confidence"],
                "reason": best["reason"],
            }
        )

    relationships.sort(
        key=lambda item: (-item["confidence"], item["knowledge_id"])
    )
    return relationships


def find_related_regulations(
    knowledge_item: dict,
    existing_items: list[dict],
    *,
    min_confidence: float = 0.5,
) -> list[dict]:
    return [
        relationship
        for relationship in build_relationships(knowledge_item, existing_items)
        if relationship["confidence"] >= min_confidence
    ]
