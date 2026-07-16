from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.report.ai_generator import REPORT_TITLE, generate_weekly_report
from app.report.builder import build_weekly_report
from app.report.generation import create_and_save_weekly_report
from app.report.storage import (
    get_latest_report,
    get_report,
    get_report_history,
    save_report,
)
from app.storage.service import StorageService, _get_service


def _empty_summary() -> dict:
    return {
        "total_changes": 0,
        "high_risk": 0,
        "medium_risk": 0,
        "low_risk": 0,
        "affected_modules": [],
    }


def _serialize_history_item(report: dict) -> dict:
    return {
        "id": report.get("id"),
        "title": report.get("title", REPORT_TITLE),
        "generated_at": report.get("generated_at", ""),
        "period": report.get("period", {}),
        "summary": report.get("summary", _empty_summary()),
    }


def register_report_routes(
    app: FastAPI,
    storage_service: StorageService | None = None,
    reports_dir: Path | str | None = None,
    build_weekly_report_fn=build_weekly_report,
    generate_weekly_report_fn=generate_weekly_report,
    create_and_save_weekly_report_fn=create_and_save_weekly_report,
    save_report_fn=save_report,
    get_latest_report_fn=get_latest_report,
    get_report_history_fn=get_report_history,
    get_report_fn=get_report,
) -> None:
    storage = storage_service or _get_service()

    @app.get("/api/reports/latest")
    def api_get_latest_report():
        report = get_latest_report_fn(reports_dir=reports_dir)
        if report is None:
            raise HTTPException(status_code=404, detail="No reports found")
        return report

    @app.get("/api/reports")
    def api_list_reports(limit: int = 20):
        history = get_report_history_fn(limit=limit, reports_dir=reports_dir)
        return [_serialize_history_item(report) for report in history]

    @app.get("/api/reports/{report_id}")
    def api_get_report(report_id: str):
        report = get_report_fn(report_id, reports_dir=reports_dir)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
        return report

    @app.post("/api/reports/generate")
    def api_generate_report():
        return create_and_save_weekly_report_fn(
            storage=storage,
            reports_dir=reports_dir,
            build_weekly_report_fn=build_weekly_report_fn,
            generate_weekly_report_fn=generate_weekly_report_fn,
            save_report_fn=save_report_fn,
        )
