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
    update_report,
)
from app.web.report_email_helper import (
    deliver_report_email,
    send_test_report_email,
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
    report_config_file: Path | str | None = None,
    notification_file: Path | str | None = None,
    email_settings_file: Path | str | None = None,
    build_weekly_report_fn=build_weekly_report,
    generate_weekly_report_fn=generate_weekly_report,
    create_and_save_weekly_report_fn=create_and_save_weekly_report,
    save_report_fn=save_report,
    get_latest_report_fn=get_latest_report,
    get_report_history_fn=get_report_history,
    get_report_fn=get_report,
    update_report_fn=update_report,
    deliver_report_email_fn=deliver_report_email,
    send_test_report_email_fn=send_test_report_email,
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
            email_settings_file=email_settings_file,
            build_weekly_report_fn=build_weekly_report_fn,
            generate_weekly_report_fn=generate_weekly_report_fn,
            save_report_fn=save_report_fn,
        )

    def _deliver_report_by_id(report_id: str) -> dict:
        report = get_report_fn(report_id, reports_dir=reports_dir)
        if report is None:
            raise HTTPException(status_code=404, detail="Report not found")
        try:
            return deliver_report_email_fn(
                report,
                reports_dir=reports_dir,
                report_config_file=report_config_file,
                notification_file=notification_file,
                email_settings_file=email_settings_file,
                update_report_fn=update_report_fn,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.post("/api/reports/{report_id}/email/send")
    def api_send_report_email(report_id: str):
        return _deliver_report_by_id(report_id)

    @app.post("/api/reports/{report_id}/email/retry")
    def api_retry_report_email(report_id: str):
        return _deliver_report_by_id(report_id)

    @app.post("/api/reports/email/test")
    def api_send_test_report_email():
        result = send_test_report_email_fn(
            report_config_file=report_config_file,
            notification_file=notification_file,
            email_settings_file=email_settings_file,
        )
        if not result.get("ok"):
            raise HTTPException(
                status_code=400,
                detail={
                    "message": result.get("message", "Test email failed."),
                    "technical_details": result.get("technical_details"),
                },
            )
        return result
