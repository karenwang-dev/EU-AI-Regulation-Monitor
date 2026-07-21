from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from app.core.paths import get_default_monitor_db_path

_RUNS_SCHEMA = """
CREATE TABLE IF NOT EXISTS monitor_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monitor_id TEXT NOT NULL,
    monitor_name TEXT NOT NULL,
    triggered_by TEXT NOT NULL,
    execution_status TEXT NOT NULL,
    change_status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    pages_checked INTEGER NOT NULL DEFAULT 0,
    pages_changed INTEGER NOT NULL DEFAULT 0,
    homepage_changed INTEGER NOT NULL DEFAULT 0,
    child_pages_changed INTEGER NOT NULL DEFAULT 0,
    pages_added INTEGER NOT NULL DEFAULT 0,
    pages_removed INTEGER NOT NULL DEFAULT 0,
    pages_failed INTEGER NOT NULL DEFAULT 0,
    snapshot_id INTEGER,
    diff_id INTEGER,
    error TEXT,
    page_results_json TEXT,
    legacy INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_monitor_runs_monitor_id
    ON monitor_runs(monitor_id);

CREATE INDEX IF NOT EXISTS idx_monitor_runs_created_at
    ON monitor_runs(created_at);
"""


def map_page_result_status(url_result: dict) -> str:
    status = url_result.get("status", "")
    if status in {"changed", "analyzed"}:
        return "changed"
    if status == "first_snapshot":
        return "baseline"
    if status == "skipped":
        return "unchanged"
    if status == "page_added":
        return "added"
    if status == "page_removed":
        return "removed"
    if status == "error":
        return "failed"
    return "unchanged"


def map_page_type(url_result: dict) -> str:
    page_change = url_result.get("page_change") or {}
    page_type = page_change.get("page_type") or url_result.get("page_type")
    if page_type:
        normalized = str(page_type).lower()
        if "child" in normalized:
            return "child"
        if "home" in normalized:
            return "homepage"
    depth = url_result.get("depth", url_result.get("discovered_depth", 0))
    return "homepage" if depth == 0 else "child"


def build_page_results(url_results: list[dict] | None) -> list[dict]:
    page_results = []
    for item in url_results or []:
        page_change = item.get("page_change") or {}
        page_results.append(
            {
                "url": item.get("url", ""),
                "page_title": item.get("title") or item.get("name") or item.get("url", ""),
                "page_type": map_page_type(item),
                "status": map_page_result_status(item),
                "snapshot_id": item.get("snapshot_id"),
                "previous_snapshot_id": item.get("previous_snapshot_id"),
                "diff_id": item.get("diff_id"),
                "content_hash": item.get("content_hash") or item.get("after_hash"),
                "error": item.get("message") if item.get("status") == "error" else None,
            }
        )
    return page_results


def derive_change_status(
    pipeline_result: dict,
    pages_changed: int,
    execution_failed: bool,
) -> str:
    if execution_failed:
        return "failed"
    if pages_changed > 0 or pipeline_result.get("status") in {"changed", "analyzed"}:
        return "changed"
    url_results = pipeline_result.get("url_results") or []
    if url_results and all(
        item.get("status") == "first_snapshot" for item in url_results
    ):
        return "baseline"
    if pipeline_result.get("status") == "first_snapshot":
        return "baseline"
    return "unchanged"


class MonitorRunStore:
    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(db_path or get_default_monitor_db_path())
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(_RUNS_SCHEMA)

    def save_run(
        self,
        *,
        monitor_id: str,
        monitor_name: str,
        triggered_by: str,
        execution_status: str,
        change_status: str,
        started_at: str,
        finished_at: str,
        duration_ms: int,
        pages_checked: int,
        pages_changed: int,
        homepage_changed: bool,
        child_pages_changed: int,
        pages_added: int = 0,
        pages_removed: int = 0,
        pages_failed: int = 0,
        snapshot_id: int | None = None,
        diff_id: int | None = None,
        error: str | None = None,
        page_results: list[dict] | None = None,
        legacy: bool = False,
    ) -> int:
        created_at = datetime.now().isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO monitor_runs (
                    monitor_id, monitor_name, triggered_by, execution_status,
                    change_status, started_at, finished_at, duration_ms,
                    pages_checked, pages_changed, homepage_changed,
                    child_pages_changed, pages_added, pages_removed,
                    pages_failed, snapshot_id, diff_id, error,
                    page_results_json, legacy, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    monitor_id,
                    monitor_name,
                    triggered_by,
                    execution_status,
                    change_status,
                    started_at,
                    finished_at,
                    duration_ms,
                    pages_checked,
                    pages_changed,
                    1 if homepage_changed else 0,
                    child_pages_changed,
                    pages_added,
                    pages_removed,
                    pages_failed,
                    snapshot_id,
                    diff_id,
                    error,
                    json.dumps(page_results or [], ensure_ascii=False),
                    1 if legacy else 0,
                    created_at,
                ),
            )
            return int(cursor.lastrowid)

    def get_run(self, run_history_id: int | str) -> dict | None:
        try:
            run_id = int(run_history_id)
        except (TypeError, ValueError):
            return None

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM monitor_runs WHERE id = ?",
                (run_id,),
            ).fetchone()

        if row is None:
            return None

        page_results_raw = row["page_results_json"]
        page_results = json.loads(page_results_raw) if page_results_raw else []
        legacy = bool(row["legacy"])

        return {
            "run_history_id": row["id"],
            "monitor_id": row["monitor_id"],
            "monitor_name": row["monitor_name"],
            "triggered_by": row["triggered_by"],
            "execution_status": row["execution_status"],
            "change_status": row["change_status"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "duration_ms": row["duration_ms"],
            "pages_checked": row["pages_checked"],
            "pages_changed": row["pages_changed"],
            "homepage_changed": bool(row["homepage_changed"]),
            "child_pages_changed": row["child_pages_changed"],
            "pages_added": row["pages_added"],
            "pages_removed": row["pages_removed"],
            "pages_failed": row["pages_failed"],
            "snapshot_id": row["snapshot_id"],
            "diff_id": row["diff_id"],
            "error": row["error"],
            "page_results": page_results,
            "page_details_available": bool(page_results) and not legacy,
            "legacy": legacy,
        }


_default_run_store: MonitorRunStore | None = None


def get_monitor_run_store(db_path: Path | None = None) -> MonitorRunStore:
    if db_path is not None:
        return MonitorRunStore(db_path=db_path)
    global _default_run_store
    if _default_run_store is None:
        _default_run_store = MonitorRunStore()
    return _default_run_store


def reset_monitor_run_store() -> None:
    global _default_run_store
    _default_run_store = None
