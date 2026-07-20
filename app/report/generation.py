from __future__ import annotations

from pathlib import Path

from app.report.ai_generator import REPORT_TITLE, generate_weekly_report
from app.report.builder import build_weekly_report
from app.report.notifier import notify_weekly_report
from app.report.storage import DEFAULT_REPORTS_DIR, save_report, update_report
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
    email_settings_file: Path | str | None = None,
    build_weekly_report_fn=build_weekly_report,
    generate_weekly_report_fn=generate_weekly_report,
    save_report_fn=save_report,
    notify_weekly_report_fn=notify_weekly_report,
    update_report_fn=update_report,
) -> dict:
    service = storage or _get_service()
    report_data = build_weekly_report_fn(storage=service)
    generated = generate_weekly_report_fn(report_data, client=client)
    stored = save_report_fn(
        assemble_stored_report(report_data, generated),
        reports_dir=reports_dir,
    )

    reports_root = (
        Path(reports_dir) if reports_dir is not None else DEFAULT_REPORTS_DIR
    )
    attachment_path = reports_root / stored["filename"]
    notification_result = {
        "sent": False,
        "skipped": True,
        "status": "Disabled",
        "reason": "Report email notification was not attempted.",
    }

    try:
        notification_result = notify_weekly_report_fn(
            stored,
            attachment_path=attachment_path,
            email_settings_file=email_settings_file,
        )
    except Exception as error:
        print(f"Weekly report email notification failed: {error}")
        notification_result = {
            "sent": False,
            "skipped": False,
            "status": "Failed",
            "reason": str(error),
        }

    return update_report_fn(
        {
            **stored,
            "email_status": notification_result.get("status", "Disabled"),
            "email_notification": notification_result,
        },
        reports_dir=reports_dir,
    )
