from __future__ import annotations

import re
from difflib import SequenceMatcher


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", str(title).strip().lower())


def _title_matches(base_title: str, candidate_title: str) -> bool:
    base = _normalize_title(base_title)
    candidate = _normalize_title(candidate_title)
    if not base or not candidate:
        return False
    if base in candidate or candidate in base:
        return True
    return SequenceMatcher(None, base, candidate).ratio() >= 0.65


def _extract_date(value: str) -> str | None:
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if "T" in cleaned:
        return cleaned.split("T", 1)[0]
    if len(cleaned) >= 10:
        return cleaned[:10]
    return cleaned


def _event_summary(item: dict, event_type: str) -> str:
    summary = str(item.get("summary", "")).strip()
    if summary:
        return summary

    title = str(item.get("title", "")).strip() or "Regulation update"
    if event_type == "EFFECTIVE":
        return f"Effective date reached for {title}"
    return f"Knowledge captured for {title}"


def build_regulation_timeline(
    title: str,
    knowledge_items: list[dict] | None = None,
) -> list[dict]:
    if knowledge_items is None:
        from app.knowledge.statistics import fetch_all_knowledge_items
        from app.storage.service import _get_service

        knowledge_items = fetch_all_knowledge_items(_get_service())

    matching_items = [
        item
        for item in knowledge_items
        if _title_matches(title, item.get("title", ""))
    ]

    events: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for item in matching_items:
        regulation_type = str(item.get("regulation_type", "")).strip() or "UPDATE"

        created_date = _extract_date(item.get("created_at", ""))
        if created_date:
            key = (created_date, regulation_type, _event_summary(item, regulation_type))
            if key not in seen:
                seen.add(key)
                events.append(
                    {
                        "date": created_date,
                        "type": regulation_type,
                        "summary": _event_summary(item, regulation_type),
                        "knowledge_id": item.get("id"),
                    }
                )

        effective_date = _extract_date(item.get("effective_date", ""))
        if effective_date:
            key = (effective_date, "EFFECTIVE", _event_summary(item, "EFFECTIVE"))
            if key not in seen:
                seen.add(key)
                events.append(
                    {
                        "date": effective_date,
                        "type": "EFFECTIVE",
                        "summary": _event_summary(item, "EFFECTIVE"),
                        "knowledge_id": item.get("id"),
                    }
                )

    events.sort(key=lambda event: event["date"])
    return events
