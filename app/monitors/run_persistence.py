from __future__ import annotations

from datetime import datetime

from app.core.logging import get_logger
from app.monitors.repository import SQLiteMonitorRepository
from app.monitors.run_store import (
    MonitorRunStore,
    build_page_results,
    derive_change_status,
)
from app.utils.datetime_utils import format_utc_iso, utc_now, utc_now_iso

logger = get_logger(__name__)


def persist_monitor_run(
    *,
    repository: SQLiteMonitorRepository,
    run_store: MonitorRunStore,
    monitor: dict,
    pipeline_result: dict,
    triggered_by: str,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> int | None:
    started = started_at or utc_now()
    finished = finished_at or utc_now()
    duration_ms = int((finished - started).total_seconds() * 1000)

    summary = pipeline_result.get("page_change_summary") or {}
    pages_checked = int(
        summary.get("pages_checked", pipeline_result.get("pages_crawled", 0))
    )
    pages_changed = int(summary.get("pages_changed", 0))
    pages_added = int(summary.get("pages_added", 0))
    pages_removed = int(summary.get("pages_removed", 0))
    homepage_changed = bool(summary.get("homepage_changed", False))
    child_pages_changed = int(summary.get("child_pages_changed", 0))
    url_results = pipeline_result.get("url_results") or []
    pages_failed = sum(1 for item in url_results if item.get("status") == "error")
    page_results = build_page_results(url_results)

    execution_failed = pipeline_result.get("status") == "error"
    execution_status = "failed" if execution_failed else "success"
    change_status = derive_change_status(
        pipeline_result,
        pages_changed,
        execution_failed,
    )

    monitor_id = monitor["id"]
    finished_iso = format_utc_iso(finished) or utc_now_iso()

    try:
        run_history_id = run_store.save_run(
            monitor_id=monitor_id,
            monitor_name=monitor.get("name", monitor_id),
            triggered_by=triggered_by,
            execution_status=execution_status,
            change_status=change_status,
            started_at=format_utc_iso(started) or utc_now_iso(),
            finished_at=finished_iso,
            duration_ms=duration_ms,
            pages_checked=pages_checked,
            pages_changed=pages_changed,
            homepage_changed=homepage_changed,
            child_pages_changed=child_pages_changed,
            pages_added=pages_added,
            pages_removed=pages_removed,
            pages_failed=pages_failed,
            snapshot_id=pipeline_result.get("snapshot_id"),
            diff_id=pipeline_result.get("diff_id"),
            error=pipeline_result.get("message")
            if execution_failed
            else None,
            page_results=page_results,
            discovery_summary=pipeline_result.get("discovery_summary"),
        )
    except Exception:
        logger.exception(
            "Failed to persist monitor run: monitor_id=%s triggered_by=%s",
            monitor_id,
            triggered_by,
        )
        return None

    repository.save_execution_state(
        monitor_id,
        execution_status=execution_status,
        last_run_at=finished_iso,
        last_change_status=change_status,
        last_pages_changed=pages_changed,
        last_pages_checked=pages_checked,
        last_snapshot_id=pipeline_result.get("snapshot_id"),
        last_diff_id=pipeline_result.get("diff_id"),
        last_error=pipeline_result.get("message") if execution_failed else None,
        last_run_history_id=str(run_history_id),
    )
    return run_history_id
