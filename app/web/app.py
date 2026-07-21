import json
from datetime import datetime
from math import ceil
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.monitors.display_helpers import (
    change_status_badge_class,
    execution_status_badge_class,
    format_category_label,
    format_change_status_label,
    format_execution_status_label,
)
from app.monitors.execution import MonitorExecutionService
from app.monitors.repository import MonitorRepository, log_monitor_repository_state
from app.monitors.run_store import get_monitor_run_store
from app.run_history import get_latest_run
from app.source.source_loader import load_monitors
from app.storage.service import StorageService, _get_service
from app.web.api import (
    _build_change_summary,
    _get_diff_by_id,
)
from app.web.monitor_api import register_monitor_routes
from app.web.run_api import register_run_routes
from app.web.knowledge_api import register_knowledge_routes
from app.knowledge.similarity import find_similar_knowledge
from app.knowledge.statistics import (
    build_knowledge_statistics,
    fetch_all_knowledge_items,
)
from app.knowledge.timeline import build_regulation_timeline
from app.web.change_helper import (
    count_changes_by_impact,
    filter_changes_by_impact,
    format_impact_label,
    is_displayable_change,
    normalize_impact,
    normalized_change_impact,
)
from app.web.insight_helper import (
    build_compliance_insights,
    build_insight_summary,
    filter_compliance_insights,
    get_insight_filter_options,
)
from app.web.knowledge_helper import resolve_related_regulations
from app.web.report_email_helper import (
    build_email_action_flags,
    build_email_config_summary,
    deliver_report_email,
    resolve_report_email_display,
    send_test_report_email,
)
from app.web.impact_ui import (
    get_dashboard_risk_card_classes,
    get_impact_badge_classes,
)
from app.config.email_settings import EMAIL_SETTINGS_FILE, load_email_settings_public
from app.web.email_settings_api import register_email_settings_routes
from app.web.report_api import register_report_routes
from app.report.ai_generator import generate_weekly_report
from app.report.builder import build_weekly_report
from app.report.storage import get_latest_report
from app.web.source_helper import (
    build_source_tree,
    enrich_changes_with_source_metadata,
    extract_discovered_depth_from_evidence,
    extract_page_type_from_evidence,
    extract_source_url_from_evidence,
    format_depth_label,
    format_page_type_label,
    extract_analysis_skipped_from_evidence,
    extract_change_kind_from_evidence,
)
from app.web.dev_change_test_api import register_change_test_site_routes
from app.core.environment import get_app_env, is_development
from app.core.paths import log_runtime_paths
from app.scheduler_status import get_scheduler_health_status
from app.config.validator import validate_configuration
from app.core.logging import get_logger
from app.version import APP_NAME, APP_VERSION


TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["dashboard_risk_card_classes"] = get_dashboard_risk_card_classes
templates.env.globals["format_category_label"] = format_category_label
templates.env.globals["change_status_badge_class"] = change_status_badge_class
templates.env.globals["impact_badge_classes"] = get_impact_badge_classes
templates.env.globals["format_impact_label"] = format_impact_label
CHANGES_PAGE_SIZE = 20
logger = get_logger(__name__)

ARCHITECTURE_COMPONENTS = [
    {
        "name": "Web Dashboard",
        "description": "Jinja2 UI for monitors, changes, knowledge, insights, and reports.",
    },
    {
        "name": "FastAPI",
        "description": "HTTP server, REST APIs, health checks, and page routing.",
    },
    {
        "name": "Scheduler",
        "description": "APScheduler jobs for daily/weekly monitors and report generation.",
    },
    {
        "name": "Crawler",
        "description": "Firecrawl-based fetching with caching and link discovery.",
    },
    {
        "name": "AI Analyzer",
        "description": "OpenAI impact analysis and regulation extraction.",
    },
    {
        "name": "Knowledge Base",
        "description": "Structured regulation storage, search, and relationships.",
    },
    {
        "name": "Report Generator",
        "description": "Weekly report assembly, AI narrative, and email delivery.",
    },
    {
        "name": "Storage",
        "description": "SQLite database, raw snapshots, and report JSON files.",
    },
]


def _check_database_health(storage: StorageService) -> str:
    try:
        with storage._connect() as connection:
            connection.execute("SELECT 1").fetchone()
        return "ok"
    except Exception:
        return "error"


def _build_health_payload(storage: StorageService) -> dict:
    database_status = _check_database_health(storage)
    scheduler_status = get_scheduler_health_status()
    config_result = validate_configuration()
    configuration_status = config_result["status"]
    missing_config = config_result["missing"]

    if database_status == "error":
        overall_status = "error"
    elif configuration_status != "ok":
        overall_status = "warning"
    else:
        overall_status = "ok"

    return {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "database": database_status,
        "scheduler": scheduler_status,
        "configuration": configuration_status,
        "missing_config": missing_config,
    }


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


def _count_changes_by_impact(storage: StorageService) -> dict[str, int]:
    return count_changes_by_impact(
        _get_changes_for_dashboard(storage, limit=None)
    )


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


def _format_dashboard_timestamp(timestamp: str) -> str:
    if not timestamp:
        return "N/A"

    try:
        parsed = datetime.fromisoformat(timestamp)
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return timestamp or "N/A"


def _build_monitoring_status_display(last_run: dict | None) -> str:
    scheduler_status = get_scheduler_health_status()
    if scheduler_status == "running":
        return "Running"

    if not last_run:
        return "N/A"

    failed_count = last_run.get("failed_count", 0)
    if failed_count:
        return "Completed with failures"

    return "Completed successfully"


def _build_dashboard_recent_activity(
    last_run: dict | None,
    *,
    reports_dir: Path | None = None,
) -> dict:
    latest_report = get_latest_report(reports_dir=reports_dir)

    return {
        "last_monitoring_display": (
            _format_dashboard_timestamp(last_run.get("timestamp", ""))
            if last_run
            else "N/A"
        ),
        "last_monitoring_run_id": (
            (
                last_run.get("primary_run_id")
                or (
                    last_run.get("run_ids", [None])[-1]
                    if last_run.get("run_ids")
                    else None
                )
            )
            if last_run
            else None
        ),
        "changed_regulations_display": (
            str(last_run.get("changed_count", 0))
            if last_run
            else "N/A"
        ),
        "latest_report_display": (
            _format_report_timestamp(latest_report.get("generated_at", ""))
            if latest_report
            else "N/A"
        ),
        "monitoring_status_display": _build_monitoring_status_display(last_run),
    }


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
            impact_data = analysis["analysis"] if analysis else {}
            monitor_info = monitor_map.get(diff["source_id"], {})
            snapshot = _get_snapshot_by_id(storage, diff["new_snapshot_id"])
            source_url = extract_source_url_from_evidence(
                impact_data,
                snapshot,
                monitor_info,
            )
            discovered_depth = extract_discovered_depth_from_evidence(
                impact_data,
                snapshot,
                monitor_info,
            )
            page_type = extract_page_type_from_evidence(
                impact_data,
                snapshot,
                monitor_info,
            )
            analysis_skipped = extract_analysis_skipped_from_evidence(impact_data)
            change_kind = extract_change_kind_from_evidence(impact_data)
            impact_level = normalized_change_impact(
                {
                    "analysis": impact_data,
                    "impact_level": impact_data.get("impact_level"),
                    "impact": impact_data.get("impact"),
                }
            )
            change_record = {
                "diff_id": diff["id"],
                "analysis_id": analysis["id"] if analysis else None,
                "regulation_name": monitor_info.get(
                    "name",
                    diff["source_id"],
                ),
                "source_id": diff["source_id"],
                "date": diff["created_at"],
                "analysis": impact_data,
                "impact_level": impact_level,
                "impact_label": format_impact_label(impact_level),
                "analysis_skipped": analysis_skipped,
                "change_kind": change_kind or "changed",
                "change_kind_label": (change_kind or "changed").replace("_", " ").title(),
                "affected_modules": impact_data.get("affected_modules", []),
                "keywords": monitor_info.get("keywords", []),
                "summary": _build_change_summary(diff),
                "source_url": source_url,
                "discovered_depth": discovered_depth,
                "depth_label": format_depth_label(discovered_depth),
                "page_type": page_type,
                "page_type_label": format_page_type_label(page_type),
            }

            if not is_displayable_change(change_record):
                continue

            changes.append(change_record)

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
        filtered = filter_changes_by_impact(filtered, impact)

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


def _format_knowledge_timestamp(timestamp: str) -> str:
    if not timestamp:
        return "N/A"

    try:
        parsed = datetime.fromisoformat(timestamp)
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return timestamp


def _get_knowledge_filter_options(storage: StorageService) -> tuple[list[str], list[str]]:
    with storage._connect() as connection:
        category_rows = connection.execute(
            """
            SELECT DISTINCT category
            FROM knowledge_items
            WHERE category IS NOT NULL AND category != ''
            ORDER BY category
            """
        ).fetchall()
        module_rows = connection.execute(
            "SELECT modules_json FROM knowledge_items"
        ).fetchall()

    categories = [row["category"] for row in category_rows]
    modules: set[str] = set()
    for row in module_rows:
        for module in json.loads(row["modules_json"] or "[]"):
            if str(module).strip():
                modules.add(str(module).strip())

    return categories, sorted(modules)


def _enrich_knowledge_list_items(
    storage: StorageService,
    items: list[dict],
) -> list[dict]:
    enriched: list[dict] = []
    for item in items:
        full_item = storage.get_knowledge_item(item["id"]) or {}
        created_at = full_item.get("created_at", "")
        enriched.append(
            {
                **item,
                "created_at": created_at,
                "created_at_display": _format_knowledge_timestamp(created_at),
            }
        )
    return enriched


def _get_diff_id_for_snapshot(
    storage: StorageService,
    snapshot_id: int | None,
) -> int | None:
    if snapshot_id is None:
        return None

    with storage._connect() as connection:
        row = connection.execute(
            """
            SELECT id FROM diffs
            WHERE new_snapshot_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (snapshot_id,),
        ).fetchone()

    if row is None:
        return None

    return row["id"]


def _format_report_timestamp(timestamp: str) -> str:
    if not timestamp:
        return "N/A"

    try:
        parsed = datetime.fromisoformat(timestamp)
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return timestamp


def create_dashboard_app(
    storage_service: StorageService | None = None,
    history_file: Path | None = None,
    monitors_file: Path | None = None,
    monitors_repository: MonitorRepository | None = None,
    execution_service: MonitorExecutionService | None = None,
    reports_dir: Path | None = None,
    report_config_file: Path | None = None,
    notification_file: Path | None = None,
    email_settings_file: Path | None = None,
    build_weekly_report_fn=None,
    generate_weekly_report_fn=None,
    deliver_report_email_fn=None,
    send_test_report_email_fn=None,
    settings_send_email_fn=None,
) -> FastAPI:
    storage = storage_service or _get_service()
    app = FastAPI(title="AI Regulation Monitor Dashboard")

    if monitors_repository is None and monitors_file is not None:
        from app.monitors.repository import get_monitor_repository

        monitors_repository = get_monitor_repository(
            db_path=storage.db_path,
            seed_file=monitors_file,
        )
    elif monitors_repository is None:
        from app.monitors.repository import get_monitor_repository

        monitors_repository = get_monitor_repository(db_path=storage.db_path)

    from app.monitors.repository import set_monitor_repository

    set_monitor_repository(monitors_repository)

    @app.on_event("startup")
    def validate_app_configuration() -> None:
        result = validate_configuration()
        if result["missing"]:
            logger.warning(
                "Missing required configuration: %s",
                ", ".join(result["missing"]),
            )
        for warning in result["warnings"]:
            logger.warning(warning)
        if result["status"] == "ok":
            logger.info("Configuration validation passed")

    if execution_service is None:
        from app.core.paths import PROJECT_ROOT
        from app.run_history import RUN_HISTORY_FILE

        execution_service = MonitorExecutionService(
            repository=monitors_repository,
            history_file=(
                history_file.resolve()
                if history_file is not None
                else (PROJECT_ROOT / RUN_HISTORY_FILE).resolve()
            ),
            run_store=get_monitor_run_store(db_path=storage.db_path),
        )

    register_monitor_routes(
        app,
        monitors_file=monitors_file,
        monitors_repository=monitors_repository,
        execution_service=execution_service,
    )
    register_run_routes(
        app,
        run_store=get_monitor_run_store(db_path=storage.db_path),
    )
    register_knowledge_routes(app, storage_service=storage)
    register_report_routes(
        app,
        storage_service=storage,
        reports_dir=reports_dir,
        report_config_file=report_config_file,
        notification_file=notification_file,
        email_settings_file=email_settings_file or EMAIL_SETTINGS_FILE,
        build_weekly_report_fn=build_weekly_report_fn or build_weekly_report,
        generate_weekly_report_fn=generate_weekly_report_fn or generate_weekly_report,
        deliver_report_email_fn=deliver_report_email_fn or deliver_report_email,
        send_test_report_email_fn=send_test_report_email_fn or send_test_report_email,
    )
    register_email_settings_routes(
        app,
        email_settings_file=email_settings_file or EMAIL_SETTINGS_FILE,
        send_email_fn=settings_send_email_fn,
    )
    register_change_test_site_routes(app)

    @app.on_event("startup")
    def configure_change_test_site_state() -> None:
        app.state.change_test_site_base_url = ""
        routes_registered = bool(
            getattr(app.state, "change_test_site_routes_registered", False)
        )
        app_env = get_app_env()
        dev_mode = is_development()
        logger.info("APP_ENV=%s", app_env)
        logger.info("Development mode=%s", dev_mode)
        logger.info(
            "Development test site routes registered=%s",
            routes_registered,
        )
        if routes_registered:
            route_paths = getattr(app.state, "change_test_site_route_paths", [])
            for route_path in sorted(route_paths):
                logger.info("Development test site route: %s", route_path)
        if routes_registered and not dev_mode:
            logger.info(
                "Change test site endpoints are gated until APP_ENV is "
                "development, dev, or test."
            )
        log_runtime_paths(prefix="startup")
        log_monitor_repository_state(
            repository=monitors_repository,
            prefix="startup",
        )

    def _latest_run():
        if history_file:
            return get_latest_run(history_file=history_file)
        return get_latest_run()

    @app.get("/health")
    def health_check():
        payload = _build_health_payload(storage)
        if payload["status"] == "error":
            status_code = 503
        else:
            status_code = 200
        return JSONResponse(content=payload, status_code=status_code)

    @app.get("/about")
    def about_page(request: Request):
        config_result = validate_configuration()
        return templates.TemplateResponse(
            request,
            "about.html",
            {
                "title": "About",
                "active_page": "about",
                "app_name": APP_NAME,
                "app_version": APP_VERSION,
                "config_status": config_result["status"],
                "missing_config": config_result["missing"],
                "config_warnings": config_result["warnings"],
                "architecture_components": ARCHITECTURE_COMPONENTS,
            },
        )

    @app.get("/runs/{run_history_id}")
    def run_details_page(request: Request, run_history_id: int):
        run_store = get_monitor_run_store(db_path=storage.db_path)
        run = run_store.get_run(run_history_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")

        page_results = []
        for page in run.get("page_results", []):
            page_results.append(
                {
                    **page,
                    "badge_class": change_status_badge_class(page.get("status")),
                    "status_label": format_change_status_label(page.get("status")),
                }
            )
        run = {**run, "page_results": page_results}

        duration_ms = run.get("duration_ms", 0)
        duration_display = (
            f"{duration_ms / 1000:.1f}s" if duration_ms >= 1000 else f"{duration_ms}ms"
        )

        return templates.TemplateResponse(
            request,
            "run_details.html",
            {
                "title": f"Run {run_history_id}",
                "active_page": "monitors",
                "run": run,
                "execution_badge": execution_status_badge_class(
                    run.get("execution_status")
                ),
                "execution_label": format_execution_status_label(
                    run.get("execution_status")
                ),
                "change_badge": change_status_badge_class(run.get("change_status")),
                "change_label": format_change_status_label(run.get("change_status")),
                "started_display": _format_dashboard_timestamp(run.get("started_at", "")),
                "finished_display": _format_dashboard_timestamp(run.get("finished_at", "")),
                "duration_display": duration_display,
            },
        )

    @app.get("/")
    def dashboard_home(request: Request):
        latest_run = _latest_run()
        monitors = load_monitors()
        impact_counts = _count_changes_by_impact(storage)

        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "title": "Dashboard",
                "active_page": "dashboard",
                "monitor_count": len(monitors),
                "todays_changes_count": _count_todays_changes(storage),
                "high_risk_count": impact_counts.get("HIGH", 0),
                "medium_risk_count": impact_counts.get("MEDIUM", 0),
                "low_risk_count": impact_counts.get("LOW", 0),
                "recent_activity": _build_dashboard_recent_activity(
                    latest_run,
                    reports_dir=reports_dir,
                ),
            },
        )

    @app.get("/monitors")
    def monitors_page(request: Request):
        monitors = load_monitors()
        enabled_count = sum(1 for monitor in monitors if monitor.get("enabled"))
        last_run = _latest_run()
        return templates.TemplateResponse(
            request,
            "monitor_manage.html",
            {
                "title": "Monitors",
                "active_page": "monitors",
                "total_monitors": len(monitors),
                "enabled_count": enabled_count,
                "disabled_count": len(monitors) - enabled_count,
                "recent_updates_count": (
                    last_run.get("changed_count", 0) if last_run else 0
                ),
                "is_development": is_development(),
            },
        )

    @app.get("/manage-monitors")
    def manage_monitors_redirect():
        return RedirectResponse(url="/monitors", status_code=301)

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

    @app.get("/knowledge")
    def knowledge_page(
        request: Request,
        q: str = "",
        category: str = "",
        module: str = "",
        impact: str = "",
    ):
        all_insights = build_compliance_insights(storage)
        categories, modules = get_insight_filter_options(all_insights)
        filtered_insights = filter_compliance_insights(
            all_insights,
            query=q,
            category=category,
            module=module,
            impact=impact,
        )
        summary = build_insight_summary(filtered_insights)

        return templates.TemplateResponse(
            request,
            "knowledge.html",
            {
                "title": "Knowledge Base",
                "active_page": "knowledge",
                "items": filtered_insights,
                "summary": summary,
                "query": q,
                "category_filter": category,
                "module_filter": module,
                "impact_filter": impact,
                "categories": categories,
                "modules": modules,
            },
        )

    @app.get("/reports")
    def reports_page(request: Request):
        report = get_latest_report(reports_dir=reports_dir)
        summary = report.get("summary", {}) if report else {
            "total_changes": 0,
            "high_risk": 0,
            "medium_risk": 0,
            "low_risk": 0,
            "affected_modules": [],
        }
        report_view = None
        key_changes = []

        if report:
            report_view = {
                **report,
                "generated_at_display": _format_report_timestamp(
                    report.get("generated_at", "")
                ),
            }
            key_changes = report.get("key_changes", [])

        email_display = resolve_report_email_display(
            report,
            report_config_file=report_config_file,
            notification_file=notification_file,
            email_settings_file=email_settings_file or EMAIL_SETTINGS_FILE,
        )
        email_config = build_email_config_summary(
            report_config_file=report_config_file,
            notification_file=notification_file,
            email_settings_file=email_settings_file or EMAIL_SETTINGS_FILE,
        )
        email_actions = build_email_action_flags(report, email_display)
        email_settings = load_email_settings_public(
            email_settings_file or EMAIL_SETTINGS_FILE
        )

        return templates.TemplateResponse(
            request,
            "report.html",
            {
                "title": "Weekly Reports",
                "active_page": "reports",
                "report": report_view,
                "summary": summary,
                "key_changes": key_changes,
                "email_display": email_display,
                "email_config": email_config,
                "email_actions": email_actions,
                "email_settings": email_settings,
            },
        )

    @app.get("/insights")
    def insights_redirect(request: Request):
        query = request.url.query
        target = f"/knowledge?{query}" if query else "/knowledge"
        return RedirectResponse(url=target, status_code=301)

    @app.get("/knowledge/statistics")
    def knowledge_statistics_page(request: Request):
        items = fetch_all_knowledge_items(storage)
        statistics = build_knowledge_statistics(items)

        return templates.TemplateResponse(
            request,
            "knowledge_statistics.html",
            {
                "title": "Knowledge Statistics",
                "active_page": "knowledge",
                "statistics": statistics,
            },
        )

    @app.get("/knowledge/{item_id}")
    def knowledge_detail_page(request: Request, item_id: int):
        item = storage.get_knowledge_item(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Knowledge item not found")

        monitor_map = _get_monitor_map()
        monitor = monitor_map.get(item.get("source_id", ""), {})
        snapshot = _get_snapshot_by_id(storage, item.get("snapshot_id"))
        source_url = snapshot.get("url", "") if snapshot else monitor.get("url", "")

        detail_item = {
            **item,
            "created_at_display": _format_knowledge_timestamp(
                item.get("created_at", "")
            ),
        }

        all_items = fetch_all_knowledge_items(storage)
        similar_items = find_similar_knowledge(item, all_items, threshold=0.8)
        timeline = build_regulation_timeline(
            item.get("title", ""),
            knowledge_items=all_items,
        )
        related_regulations = resolve_related_regulations(item, storage)

        return templates.TemplateResponse(
            request,
            "knowledge_detail.html",
            {
                "title": item.get("title") or "Knowledge Detail",
                "active_page": "knowledge",
                "item": detail_item,
                "monitor_name": monitor.get("name", item.get("source_id", "")),
                "source_url": source_url,
                "diff_id": _get_diff_id_for_snapshot(
                    storage,
                    item.get("snapshot_id"),
                ),
                "similar_items": similar_items,
                "timeline": timeline,
                "related_regulations": related_regulations,
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
