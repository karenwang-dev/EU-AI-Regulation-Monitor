from __future__ import annotations

import json
from datetime import datetime, timedelta

from app.knowledge.statistics import fetch_all_knowledge_items
from app.source.source_loader import load_monitors
from app.storage.service import StorageService, _get_service
from app.web.insight_helper import (
    IMPACT_SORT_ORDER,
    VALID_IMPACT_LEVELS,
    build_compliance_insight,
)
from app.web.source_helper import extract_source_url_from_evidence

DEFAULT_PERIOD_DAYS = 7


def _parse_boundary(value, *, end_of_day: bool) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Date value cannot be empty")
        if "T" in cleaned:
            parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        else:
            parsed = datetime.fromisoformat(cleaned[:10])
    else:
        raise TypeError(f"Unsupported date type: {type(value)!r}")

    if end_of_day and "T" not in str(value):
        return parsed.replace(hour=23, minute=59, second=59, microsecond=999999)

    return parsed


def _resolve_period(
    start_date=None,
    end_date=None,
) -> tuple[dict[str, str], datetime, datetime]:
    if end_date is None:
        end = datetime.now()
    else:
        end = _parse_boundary(
            end_date,
            end_of_day="T" not in str(end_date),
        )

    if start_date is None:
        start = end - timedelta(days=DEFAULT_PERIOD_DAYS)
    else:
        start = _parse_boundary(start_date, end_of_day=False)

    if start > end:
        start, end = end, start

    return (
        {
            "start": start.date().isoformat(),
            "end": end.date().isoformat(),
        },
        start,
        end,
    )


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    try:
        return datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError:
        if len(cleaned) >= 10:
            try:
                return datetime.fromisoformat(cleaned[:10])
            except ValueError:
                return None
    return None


def _in_period(
    timestamp: str | None,
    start: datetime,
    end: datetime,
) -> bool:
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return False
    return start <= parsed <= end


def _normalize_impact_level(value) -> str:
    normalized = str(value or "NONE").strip().upper()
    if normalized not in VALID_IMPACT_LEVELS:
        return "NONE"
    return normalized


def _normalize_string_list(values) -> list[str]:
    if not values:
        return []
    return [
        str(value).strip()
        for value in values
        if str(value).strip()
    ]


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip() or default


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


def _build_knowledge_by_snapshot(
    storage: StorageService,
) -> dict[int, dict]:
    knowledge_by_snapshot: dict[int, dict] = {}
    for item in fetch_all_knowledge_items(storage):
        snapshot_id = item.get("snapshot_id")
        if snapshot_id is None:
            continue
        knowledge_by_snapshot[int(snapshot_id)] = item
    return knowledge_by_snapshot


def _fetch_all_diffs(storage: StorageService) -> list[dict]:
    diffs: list[dict] = []
    for monitor in load_monitors():
        diffs.extend(storage.get_diff_history(monitor["id"]))
    diffs.sort(key=lambda diff: diff.get("created_at", ""), reverse=True)
    return diffs


def _build_change_entry(
    diff: dict,
    storage: StorageService,
    knowledge_by_snapshot: dict[int, dict],
    monitor_map: dict[str, dict],
) -> dict:
    snapshot_id = diff.get("new_snapshot_id")
    knowledge = knowledge_by_snapshot.get(snapshot_id)
    analysis = _lookup_analysis_for_snapshot(storage, snapshot_id) or {}
    extraction = analysis.get("regulation_extraction") or {}
    insight = (
        build_compliance_insight(knowledge, storage)
        if knowledge
        else None
    )
    monitor = monitor_map.get(diff.get("source_id", ""), {})
    snapshot = (
        storage.get_snapshot_by_id(snapshot_id)
        if snapshot_id is not None
        else None
    )

    title = _safe_text(
        (knowledge or {}).get("title")
        or extraction.get("title")
        or monitor.get("name")
        or diff.get("source_id")
    )
    category = _safe_text(
        (knowledge or {}).get("category")
        or extraction.get("category")
        or monitor.get("category")
    )
    impact_level = _normalize_impact_level(analysis.get("impact_level"))
    confidence = _safe_text(
        (knowledge or {}).get("confidence")
        or analysis.get("confidence")
        or extraction.get("confidence")
    )

    if insight:
        modules = insight.get("affected_modules", [])
        actions = insight.get("recommended_actions", [])
    else:
        modules = _normalize_string_list(analysis.get("affected_modules"))
        actions = _normalize_string_list(analysis.get("recommended_actions"))

    source_url = extract_source_url_from_evidence(analysis, snapshot, monitor)

    return {
        "title": title,
        "category": category,
        "impact_level": impact_level,
        "confidence": confidence,
        "modules": modules,
        "actions": actions,
        "source_url": source_url,
        "knowledge_id": knowledge.get("id") if knowledge else None,
    }


def _dedupe_key(change: dict) -> str:
    title = _safe_text(change.get("title")).lower()
    if title:
        return f"title:{title}"
    return f"url:{_safe_text(change.get('source_url')).lower()}"


def _dedupe_changes(changes: list[dict]) -> list[dict]:
    best_by_key: dict[str, dict] = {}

    for change in changes:
        key = _dedupe_key(change)
        existing = best_by_key.get(key)
        if existing is None:
            best_by_key[key] = change
            continue

        existing_rank = IMPACT_SORT_ORDER.get(
            existing.get("impact_level", "NONE"),
            99,
        )
        current_rank = IMPACT_SORT_ORDER.get(
            change.get("impact_level", "NONE"),
            99,
        )
        if current_rank < existing_rank:
            best_by_key[key] = change
            continue
        if current_rank == existing_rank and not existing.get("knowledge_id"):
            if change.get("knowledge_id"):
                best_by_key[key] = change

    return list(best_by_key.values())


def _sort_changes(changes: list[dict]) -> list[dict]:
    return sorted(
        changes,
        key=lambda change: (
            IMPACT_SORT_ORDER.get(change.get("impact_level", "NONE"), 99),
            _safe_text(change.get("title")).lower(),
        ),
    )


def _build_summary(changes: list[dict]) -> dict:
    affected_modules = sorted(
        {
            module
            for change in changes
            for module in change.get("modules", [])
            if str(module).strip()
        }
    )

    return {
        "total_changes": len(changes),
        "high_risk": sum(
            1 for change in changes if change.get("impact_level") == "HIGH"
        ),
        "medium_risk": sum(
            1 for change in changes if change.get("impact_level") == "MEDIUM"
        ),
        "low_risk": sum(
            1 for change in changes if change.get("impact_level") == "LOW"
        ),
        "affected_modules": affected_modules,
    }


def build_weekly_report(
    start_date=None,
    end_date=None,
    *,
    storage: StorageService | None = None,
) -> dict:
    service = storage or _get_service()
    period, period_start, period_end = _resolve_period(start_date, end_date)

    knowledge_by_snapshot = _build_knowledge_by_snapshot(service)
    monitor_map = {monitor["id"]: monitor for monitor in load_monitors()}

    changes: list[dict] = []
    for diff in _fetch_all_diffs(service):
        if not diff.get("changed"):
            continue
        if not _in_period(diff.get("created_at"), period_start, period_end):
            continue

        changes.append(
            _build_change_entry(
                diff,
                service,
                knowledge_by_snapshot,
                monitor_map,
            )
        )

    changes = _sort_changes(_dedupe_changes(changes))

    return {
        "period": period,
        "summary": _build_summary(changes),
        "changes": changes,
    }
