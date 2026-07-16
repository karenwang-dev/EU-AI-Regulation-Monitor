from __future__ import annotations

from pathlib import Path

from app.report.ai_generator import REPORT_TITLE, generate_weekly_report
from app.report.builder import build_weekly_report
from app.report.storage import save_report
from app.storage.service import StorageService, _get_service


def _empty_summary() -> dict:
    return {
        "total_changes": 0,
        "high_risk": 0,
        "medium_risk": 0,
        "low_risk": 0,
        "affected_modules": [],
    }


def assemble_stored_report(report_data: dict, generated: dict) -> dict:
    changes_by_title = {
        str(change.get("title", "")).strip().lower(): change
        for change in report_data.get("changes", [])
        if isinstance(change, dict)
    }

    key_changes = []
    for item in generated.get("key_changes", []):
        if not isinstance(item, dict):
            continue
        match = changes_by_title.get(
            str(item.get("title", "")).strip().lower(),
            {},
        )
        key_changes.append(
            {
                **item,
                "source_url": match.get("source_url", ""),
                "knowledge_id": match.get("knowledge_id"),
            }
        )

    if not key_changes:
        key_changes = [
            {
                "title": change.get("title", ""),
                "summary": "",
                "impact_level": change.get("impact_level", "NONE"),
                "affected_modules": change.get("modules", []),
                "recommended_actions": change.get("actions", []),
                "source_url": change.get("source_url", ""),
                "knowledge_id": change.get("knowledge_id"),
            }
            for change in report_data.get("changes", [])
            if isinstance(change, dict)
        ]

    return {
        "title": generated.get("title", REPORT_TITLE),
        "generated_at": generated.get("generated_at", ""),
        "period": report_data.get("period", {}),
        "summary": report_data.get("summary", _empty_summary()),
        "executive_summary": generated.get("executive_summary", ""),
        "key_changes": key_changes,
        "risk_summary": generated.get("risk_summary", ""),
    }


def create_and_save_weekly_report(
    *,
    storage: StorageService | None = None,
    client=None,
    reports_dir: Path | str | None = None,
    build_weekly_report_fn=build_weekly_report,
    generate_weekly_report_fn=generate_weekly_report,
    save_report_fn=save_report,
) -> dict:
    service = storage or _get_service()
    report_data = build_weekly_report_fn(storage=service)
    generated = generate_weekly_report_fn(report_data, client=client)
    return save_report_fn(
        assemble_stored_report(report_data, generated),
        reports_dir=reports_dir,
    )
