import json
from datetime import datetime
from math import ceil
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
from app.web.source_helper import (
    build_source_tree,
    enrich_changes_with_source_metadata,
    extract_discovered_depth_from_evidence,
    extract_source_url_from_evidence,
    format_depth_label,
)


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
CHANGES_PAGE_SIZE = 20


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


def _get_snapshot_by_id(
    storage: StorageService,
    snapshot_id: int,
) -> dict | None:
    with storage._connect() as connection:
        row = connection.execute(
            "SELECT * FROM snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()

    if row is None:
        return None

    return storage._row_to_snapshot(row)


def _count_high_risk_analyses(storage: StorageService) -> int:
    return _count_analyses_by_impact(storage).get("HIGH", 0)


def _count_analyses_by_impact(storage: StorageService) -> dict[str, int]:
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

    with storage._connect() as connection:
        rows = connection.execute(
            "SELECT analysis_json FROM analyses"
        ).fetchall()

    for row in rows:
        analysis = json.loads(row["analysis_json"])
        level = str(analysis.get("impact_level", "NONE")).upper()
        if level in counts:
            counts[level] += 1

    return counts


def _count_todays_changes(storage: StorageService) -> int:
    today_prefix = datetime.now().strftime("%Y-%m-%d")

    with storage._connect() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) FROM diffs
            WHERE created_at LIKE ?
            """,
            (f"{today_prefix}%",),
        ).fetchone()

    return row[0] if row else 0


def _format_last_run_timestamp(last_run: dict | None) -> str:
    if not last_run:
        return "Never"

    timestamp = last_run.get("timestamp", "")
    if not timestamp:
        return "Unknown"

    try:
        parsed = datetime.fromisoformat(timestamp)
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return timestamp


def _get_monitor_map() -> dict[str, dict]:
    return {monitor["id"]: monitor for monitor in load_monitors()}


def _get_changes_for_dashboard(
    storage: StorageService,
    limit: int | None = 50,
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
            monitor_info = monitor_map.get(diff["source_id"], {})
            snapshot = _get_snapshot_by_id(storage, diff["new_snapshot_id"])
            source_url = extract_source_url_from_evidence(
                impact,
                snapshot,
                monitor_info,
            )
            discovered_depth = extract_discovered_depth_from_evidence(
                impact,
                snapshot,
                monitor_info,
            )

            changes.append(
                {
                    "diff_id": diff["id"],
                    "analysis_id": analysis["id"] if analysis else None,
                    "regulation_name": monitor_info.get(
                        "name",
                        diff["source_id"],
                    ),
                    "source_id": diff["source_id"],
                    "date": diff["created_at"],
                    "impact_level": impact.get("impact_level", "NONE"),
                    "affected_modules": impact.get("affected_modules", []),
                    "keywords": monitor_info.get("keywords", []),
                    "summary": _build_change_summary(diff),
                    "source_url": source_url,
                    "discovered_depth": discovered_depth,
                    "depth_label": format_depth_label(discovered_depth),
                }
            )

    changes.sort(key=lambda item: item["date"], reverse=True)
    changes = enrich_changes_with_source_metadata(changes)

    if limit is None:
        return changes

    return changes[:limit]


def _filter_changes(
    changes: list[dict],
    query: str = "",
    impact: str = "",
) -> list[dict]:
    filtered = changes

    if query.strip():
        needle = query.strip().lower()
        filtered = [
            change
            for change in filtered
            if needle in change["regulation_name"].lower()
            or needle in change["source_id"].lower()
            or needle in change.get("summary", "").lower()
            or needle in " ".join(change.get("keywords", [])).lower()
            or needle in " ".join(change.get("affected_modules", [])).lower()
        ]

    if impact.strip():
        impact_value = impact.strip().upper()
        filtered = [
            change
            for change in filtered
            if str(change.get("impact_level", "NONE")).upper() == impact_value
        ]

    return filtered


def _paginate_changes(
    changes: list[dict],
    page: int,
    page_size: int = CHANGES_PAGE_SIZE,
) -> dict:
    total_items = len(changes)
    total_pages = max(1, ceil(total_items / page_size)) if total_items else 1
    current_page = max(1, min(page, total_pages))
    start = (current_page - 1) * page_size
    end = start + page_size

    return {
        "items": changes[start:end],
        "page": current_page,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
    }


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
        impact_counts = _count_analyses_by_impact(storage)

        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "title": "Dashboard",
                "active_page": "dashboard",
                "monitor_count": len(monitors),
                "last_run_display": _format_last_run_timestamp(latest_run),
                "last_run": latest_run,
                "todays_changes_count": _count_todays_changes(storage),
                "high_risk_count": impact_counts.get("HIGH", 0),
                "medium_risk_count": impact_counts.get("MEDIUM", 0),
                "low_risk_count": impact_counts.get("LOW", 0),
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
                "active_page": "monitors",
                "monitors": monitors,
            },
        )

    @app.get("/changes")
    def changes_page(
        request: Request,
        q: str = "",
        impact: str = "",
        page: int = 1,
    ):
        all_changes = _get_changes_for_dashboard(storage, limit=None)
        filtered_changes = _filter_changes(all_changes, query=q, impact=impact)
        pagination = _paginate_changes(filtered_changes, page=page)

        return templates.TemplateResponse(
            request,
            "changes.html",
            {
                "title": "Changes",
                "active_page": "changes",
                "changes": pagination["items"],
                "query": q,
                "impact_filter": impact,
                "page": pagination["page"],
                "total_pages": pagination["total_pages"],
                "total_items": pagination["total_items"],
                "page_size": pagination["page_size"],
            },
        )

    @app.get("/manage-monitors")
    def manage_monitors_page(request: Request):
        return templates.TemplateResponse(
            request,
            "monitor_manage.html",
            {
                "title": "Manage Monitors",
                "active_page": "manage",
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
        analysis_data = analysis["analysis"] if analysis else None
        snapshot = _get_snapshot_by_id(storage, diff["new_snapshot_id"])
        source_tree = build_source_tree(
            analysis_data.get("evidence", []) if analysis_data else None,
            monitor,
            diff=diff,
            monitor_map=monitor_map,
            snapshot=snapshot,
        )
        regulation_extraction = None
        if analysis_data:
            regulation_extraction = analysis_data.get("regulation_extraction")

        return templates.TemplateResponse(
            request,
            "detail.html",
            {
                "title": "Change Detail",
                "active_page": "changes",
                "diff": diff,
                "analysis": analysis_data,
                "analysis_id": analysis["id"] if analysis else None,
                "source_tree": source_tree,
                "regulation_extraction": regulation_extraction,
                "regulation_name": monitor.get("name", diff["source_id"]),
                "monitor_url": monitor.get("url", ""),
                "change_date": diff.get("created_at", ""),
            },
        )

    return app


app = create_dashboard_app()
