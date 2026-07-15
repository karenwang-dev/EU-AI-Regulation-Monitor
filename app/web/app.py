import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.templating import Jinja2Templates

from app.run_history import get_latest_run
from app.source.source_loader import load_monitors
from app.storage.service import StorageService, _get_service
from app.web.api import (
    _build_change_summary,
    _get_diff_by_id,
)
from app.web.monitor_api import register_monitor_routes


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _get_analysis_by_snapshot_id(
    storage: StorageService,
    snapshot_id: int,
) -> dict | None:
    with storage._connect() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                snapshot_id,
                source_id,
                analysis_json,
                created_at
            FROM analyses
            WHERE snapshot_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (snapshot_id,),
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row["id"],
        "snapshot_id": row["snapshot_id"],
        "source_id": row["source_id"],
        "analysis": json.loads(row["analysis_json"]),
        "created_at": row["created_at"],
    }


def _count_high_risk_analyses(storage: StorageService) -> int:
    with storage._connect() as connection:
        rows = connection.execute(
            "SELECT analysis_json FROM analyses"
        ).fetchall()

    count = 0
    for row in rows:
        analysis = json.loads(row["analysis_json"])
        if str(analysis.get("impact_level", "")).upper() == "HIGH":
            count += 1

    return count


def _get_monitor_map() -> dict[str, dict]:
    return {monitor["id"]: monitor for monitor in load_monitors()}


def _get_changes_for_dashboard(
    storage: StorageService,
    limit: int = 50,
) -> list[dict]:
    monitor_map = _get_monitor_map()
    changes = []

    for monitor in load_monitors():
        diffs = storage.get_diff_history(monitor["id"])
        for diff in diffs:
            analysis = _get_analysis_by_snapshot_id(
                storage,
                diff["new_snapshot_id"],
            )
            impact = analysis["analysis"] if analysis else {}

            changes.append(
                {
                    "diff_id": diff["id"],
                    "analysis_id": analysis["id"] if analysis else None,
                    "regulation_name": monitor_map.get(
                        diff["source_id"],
                        {},
                    ).get("name", diff["source_id"]),
                    "source_id": diff["source_id"],
                    "date": diff["created_at"],
                    "impact_level": impact.get("impact_level", "NONE"),
                    "affected_modules": impact.get("affected_modules", []),
                    "summary": _build_change_summary(diff),
                }
            )

    changes.sort(key=lambda item: item["date"], reverse=True)
    return changes[:limit]


def create_dashboard_app(
    storage_service: StorageService | None = None,
    history_file: Path | None = None,
    monitors_file: Path | None = None,
) -> FastAPI:
    storage = storage_service or _get_service()
    app = FastAPI(title="AI Regulation Monitor Dashboard")
    register_monitor_routes(app, monitors_file=monitors_file)

    def _latest_run():
        if history_file:
            return get_latest_run(history_file=history_file)
        return get_latest_run()

    @app.get("/")
    def dashboard_home(request: Request):
        latest_run = _latest_run()
        monitors = load_monitors()

        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "title": "Dashboard",
                "monitor_count": len(monitors),
                "last_run": latest_run,
                "changed_count": latest_run.get("changed_count", 0)
                if latest_run
                else 0,
                "analyzed_count": latest_run.get("analyzed_count", 0)
                if latest_run
                else 0,
                "high_risk_count": _count_high_risk_analyses(storage),
            },
        )

    @app.get("/monitors")
    def monitors_page(request: Request):
        monitors = load_monitors()
        return templates.TemplateResponse(
            request,
            "monitors.html",
            {
                "title": "Monitors",
                "monitors": monitors,
            },
        )

    @app.get("/changes")
    def changes_page(request: Request):
        changes = _get_changes_for_dashboard(storage)
        return templates.TemplateResponse(
            request,
            "changes.html",
            {
                "title": "Changes",
                "changes": changes,
            },
        )

    @app.get("/manage-monitors")
    def manage_monitors_page(request: Request):
        return templates.TemplateResponse(
            request,
            "monitor_manage.html",
            {
                "title": "Manage Monitors",
            },
        )

    @app.get("/detail/{diff_id}")
    def detail_page(request: Request, diff_id: int):
        diff = _get_diff_by_id(storage, diff_id)
        if diff is None:
            raise HTTPException(status_code=404, detail="Diff not found")

        analysis = _get_analysis_by_snapshot_id(
            storage,
            diff["new_snapshot_id"],
        )
        monitor_map = _get_monitor_map()
        monitor = monitor_map.get(diff["source_id"], {})

        return templates.TemplateResponse(
            request,
            "detail.html",
            {
                "title": "Change Detail",
                "diff": diff,
                "analysis": analysis["analysis"] if analysis else None,
                "analysis_id": analysis["id"] if analysis else None,
                "regulation_name": monitor.get("name", diff["source_id"]),
                "monitor_url": monitor.get("url", ""),
            },
        )

    return app


app = create_dashboard_app()
