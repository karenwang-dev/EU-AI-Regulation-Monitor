from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path

from app.core.logging import get_logger
from app.core.paths import PROJECT_ROOT
from app.monitors.repository import SQLiteMonitorRepository, get_monitor_repository
from app.monitors.run_persistence import persist_monitor_run
from app.monitors.run_store import derive_change_status, get_monitor_run_store
from app.pipeline import MonitoringPipeline
from app.run_history import RUN_HISTORY_FILE, save_run_history
from app.utils.datetime_utils import format_utc_iso, utc_now

logger = get_logger(__name__)


class MonitorAlreadyRunningError(Exception):
    pass


class MonitorRunPersistenceError(Exception):
    def __init__(self, message: str, *, monitor_id: str):
        super().__init__(message)
        self.monitor_id = monitor_id


class MonitorExecutionService:
    def __init__(
        self,
        repository: SQLiteMonitorRepository | None = None,
        pipeline_factory=None,
        history_file: Path | None = None,
        run_store=None,
    ):
        self.repository = repository or get_monitor_repository()
        self.pipeline_factory = pipeline_factory or MonitoringPipeline
        self.history_file = (
            Path(history_file).resolve()
            if history_file is not None
            else (PROJECT_ROOT / RUN_HISTORY_FILE).resolve()
        )
        self.run_store = run_store or get_monitor_run_store(
            db_path=self.repository.db_path
        )
        self._running: set[str] = set()
        self._lock = threading.Lock()

    def is_running(self, monitor_id: str) -> bool:
        with self._lock:
            return monitor_id in self._running

    def run_monitor(
        self,
        monitor_id: str,
        *,
        triggered_by: str = "manual_ui",
    ) -> dict:
        with self._lock:
            if monitor_id in self._running:
                raise MonitorAlreadyRunningError()
            self._running.add(monitor_id)

        try:
            return self._run_monitor_locked(monitor_id, triggered_by=triggered_by)
        finally:
            with self._lock:
                self._running.discard(monitor_id)

    def _run_monitor_locked(
        self,
        monitor_id: str,
        *,
        triggered_by: str,
    ) -> dict:
        started_at = utc_now()
        monitor = self.repository.get_by_id(monitor_id)
        if monitor is None:
            raise LookupError(f"Monitor not found: {monitor_id}")

        self.repository.save_execution_state(
            monitor_id,
            execution_status="running",
            last_change_status="running",
        )

        logger.info(
            "Monitor execution started: monitor_id=%s monitor_name=%s triggered_by=%s",
            monitor_id,
            monitor.get("name"),
            triggered_by,
        )

        error_message = None
        pipeline_result: dict
        try:
            pipeline = self.pipeline_factory()
            pipeline_result = pipeline.process_source(monitor)
        except Exception as error:
            logger.exception(
                "Monitor pipeline execution failed: monitor_id=%s",
                monitor_id,
            )
            error_message = str(error)
            pipeline_result = {
                "source_id": monitor_id,
                "name": monitor.get("name", monitor_id),
                "status": "error",
                "snapshot_id": None,
                "diff_id": None,
                "analysis_id": None,
                "message": error_message,
            }

        finished_at = utc_now()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        summary = pipeline_result.get("page_change_summary") or {}
        pages_checked = int(
            summary.get("pages_checked", pipeline_result.get("pages_crawled", 0))
        )
        pages_changed = int(summary.get("pages_changed", 0))
        homepage_changed = bool(summary.get("homepage_changed", False))
        child_pages_changed = int(summary.get("child_pages_changed", 0))
        url_results = pipeline_result.get("url_results") or []

        execution_failed = pipeline_result.get("status") == "error" or bool(
            error_message
        )
        execution_status = "failed" if execution_failed else "success"
        change_status = derive_change_status(
            pipeline_result,
            pages_changed,
            execution_failed,
        )

        try:
            run_history_id = persist_monitor_run(
                repository=self.repository,
                run_store=self.run_store,
                monitor=monitor,
                pipeline_result=pipeline_result,
                triggered_by=triggered_by,
                started_at=started_at,
                finished_at=finished_at,
            )
        except Exception as error:
            logger.exception(
                "Failed to persist monitor run: monitor_id=%s",
                monitor_id,
            )
            self._mark_execution_failed(
                monitor_id,
                finished_at=finished_at,
                error_message=str(error),
            )
            raise MonitorRunPersistenceError(
                "Failed to save monitor run",
                monitor_id=monitor_id,
            ) from error

        if run_history_id is None:
            self._mark_execution_failed(
                monitor_id,
                finished_at=finished_at,
                error_message="Run persistence returned no run_history_id",
            )
            raise MonitorRunPersistenceError(
                "Failed to save monitor run",
                monitor_id=monitor_id,
            )

        try:
            history_entry = save_run_history(
                [pipeline_result],
                history_file=self.history_file,
                run_ids=[run_history_id],
            )
        except Exception as error:
            logger.exception(
                "Failed to update run history file: monitor_id=%s history_file=%s",
                monitor_id,
                self.history_file,
            )
            self._mark_execution_failed(
                monitor_id,
                finished_at=finished_at,
                error_message=str(error),
                run_history_id=run_history_id,
                execution_status=execution_status,
                change_status=change_status,
                pages_changed=pages_changed,
                pages_checked=pages_checked,
                snapshot_id=pipeline_result.get("snapshot_id"),
                diff_id=pipeline_result.get("diff_id"),
            )
            raise MonitorRunPersistenceError(
                "Failed to save monitor run history",
                monitor_id=monitor_id,
            ) from error

        discovered_urls = [item.get("url") for item in url_results if item.get("url")]

        logger.info(
            "Monitor execution finished: monitor_id=%s monitor_name=%s "
            "triggered_by=%s discovered_urls=%s pages_checked=%s pages_changed=%s "
            "duration_ms=%s execution_status=%s change_status=%s run_history_id=%s",
            monitor_id,
            monitor.get("name"),
            triggered_by,
            discovered_urls,
            pages_checked,
            pages_changed,
            duration_ms,
            execution_status,
            change_status,
            run_history_id,
        )

        started_iso = format_utc_iso(started_at) or utc_now().isoformat()
        finished_iso = format_utc_iso(finished_at) or utc_now().isoformat()

        return {
            "monitor_id": monitor_id,
            "status": change_status,
            "change_status": change_status,
            "execution_status": execution_status,
            "pages_checked": pages_checked,
            "pages_changed": pages_changed,
            "homepage_changed": homepage_changed,
            "child_pages_changed": child_pages_changed,
            "snapshot_id": pipeline_result.get("snapshot_id"),
            "diff_id": pipeline_result.get("diff_id"),
            "started_at": started_iso,
            "finished_at": finished_iso,
            "error": error_message,
            "run_history_id": int(run_history_id),
            "duration_ms": duration_ms,
            "run_history_summary_id": history_entry.get("run_history_id"),
        }

    def _mark_execution_failed(
        self,
        monitor_id: str,
        *,
        finished_at: datetime,
        error_message: str,
        run_history_id: int | None = None,
        execution_status: str = "failed",
        change_status: str = "failed",
        pages_changed: int = 0,
        pages_checked: int = 0,
        snapshot_id: int | None = None,
        diff_id: int | None = None,
    ) -> None:
        finished_iso = format_utc_iso(finished_at) or utc_now().isoformat()
        self.repository.save_execution_state(
            monitor_id,
            execution_status=execution_status,
            last_run_at=finished_iso,
            last_change_status=change_status,
            last_pages_changed=pages_changed,
            last_pages_checked=pages_checked,
            last_snapshot_id=snapshot_id,
            last_diff_id=diff_id,
            last_error=error_message,
            last_run_history_id=str(run_history_id) if run_history_id else None,
        )
