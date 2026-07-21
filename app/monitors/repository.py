from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from app.core.logging import get_logger
from app.core.paths import PROJECT_ROOT, get_default_monitor_db_path
from app.source.source_loader import (
    MONITORS_FILE,
    SOURCES_FILE,
    normalize_legacy_source,
    validate_monitor,
)

logger = get_logger(__name__)

_MONITORS_SCHEMA = """
CREATE TABLE IF NOT EXISTS monitors (
    id TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_monitors_enabled
    ON monitors(enabled);

CREATE TABLE IF NOT EXISTS monitor_execution (
    monitor_id TEXT PRIMARY KEY,
    execution_status TEXT NOT NULL DEFAULT 'idle',
    last_run_at TEXT,
    last_status TEXT,
    last_pages_changed INTEGER DEFAULT 0,
    last_pages_checked INTEGER DEFAULT 0,
    last_snapshot_id INTEGER,
    last_diff_id INTEGER,
    last_error TEXT,
    last_run_history_id TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (monitor_id) REFERENCES monitors(id)
);
"""


class SQLiteMonitorRepository:
    repository_type = "SQLiteMonitorRepository"

    def __init__(
        self,
        db_path: Path | None = None,
        seed_file: Path | None = None,
        sources_file: Path | None = None,
    ):
        self.db_path = Path(db_path or get_default_monitor_db_path())
        self.seed_file = Path(seed_file) if seed_file else None
        self.sources_file = Path(sources_file) if sources_file else None
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self.seed_from_config()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(_MONITORS_SCHEMA)
            self._migrate_monitor_execution(connection)

    def _migrate_monitor_execution(self, connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(monitor_execution)")
        }
        if "last_change_status" not in columns:
            connection.execute(
                "ALTER TABLE monitor_execution ADD COLUMN last_change_status TEXT"
            )

    def seed_from_config(self, config_path: Path | None = None) -> int:
        if config_path is not None:
            if not config_path.exists():
                return 0
            monitors = self._load_seed_monitors(config_path, key="monitors")
            imported = self._insert_monitors(monitors)
            if imported:
                logger.info(
                    "Seeded %s new monitor(s) from %s",
                    imported,
                    config_path,
                )
            return imported

        imported = self._import_from_seed_files()
        if imported:
            logger.info(
                "Seeded %s new monitor(s) into %s",
                imported,
                self.db_path,
            )
        return imported

    def _import_from_seed_files(self) -> int:
        if self.seed_file is not None:
            imported = 0
            if self.seed_file.exists():
                monitors = self._load_seed_monitors(self.seed_file, key="monitors")
                imported = self._insert_monitors(monitors)
            if self.sources_file is not None and self.sources_file.exists():
                monitors = self._load_seed_monitors(self.sources_file, key="sources")
                imported += self._insert_monitors(monitors)
            return imported

        imported = 0
        project_seed = (PROJECT_ROOT / MONITORS_FILE).resolve()
        if project_seed.exists():
            monitors = self._load_seed_monitors(project_seed, key="monitors")
            imported = self._insert_monitors(monitors)

        if imported:
            return imported

        legacy_path = (
            self.sources_file
            if self.sources_file is not None
            else (PROJECT_ROOT / SOURCES_FILE).resolve()
        )
        if legacy_path.exists():
            monitors = self._load_seed_monitors(legacy_path, key="sources")
            return self._insert_monitors(monitors)

        return 0

    def _load_seed_monitors(self, path: Path, key: str) -> list[dict]:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

        raw_monitors = data.get(key, [])
        validated: list[dict] = []
        for index, monitor in enumerate(raw_monitors):
            normalized = normalize_legacy_source(monitor)
            validate_monitor(normalized, index=index)
            validated.append(normalized)
        return validated

    def _insert_monitors(self, monitors: list[dict]) -> int:
        now = datetime.now().isoformat()
        inserted = 0

        with self._connect() as connection:
            for monitor in monitors:
                existing = connection.execute(
                    "SELECT 1 FROM monitors WHERE id = ?",
                    (monitor["id"],),
                ).fetchone()
                if existing is not None:
                    continue

                connection.execute(
                    """
                    INSERT INTO monitors (
                        id, config_json, enabled, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        monitor["id"],
                        json.dumps(monitor, ensure_ascii=False),
                        1 if monitor.get("enabled", True) else 0,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO monitor_execution (
                        monitor_id, execution_status, updated_at
                    ) VALUES (?, 'idle', ?)
                    """,
                    (monitor["id"], now),
                )
                inserted += 1

        return inserted

    def _row_to_monitor(self, row: sqlite3.Row) -> dict:
        monitor = json.loads(row["config_json"])
        monitor["enabled"] = bool(row["enabled"])
        normalized = normalize_legacy_source(monitor)
        execution = self.get_execution_state(normalized["id"])
        if execution:
            change_status = execution.get("last_change_status") or execution.get(
                "last_status"
            )
            normalized.update(
                {
                    "execution_status": execution["execution_status"],
                    "last_run_at": execution.get("last_run_at"),
                    "last_change_status": change_status,
                    "last_status": change_status,
                    "last_run_history_id": execution.get("last_run_history_id"),
                    "last_pages_changed": execution.get("last_pages_changed", 0),
                    "last_pages_checked": execution.get("last_pages_checked", 0),
                }
            )
        else:
            normalized.update(
                {
                    "execution_status": "idle",
                    "last_run_at": None,
                    "last_change_status": None,
                    "last_status": None,
                    "last_run_history_id": None,
                    "last_pages_changed": 0,
                    "last_pages_checked": 0,
                }
            )
        return normalized

    def list_all(self) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM monitors ORDER BY id"
            ).fetchall()

        monitors = [self._row_to_monitor(row) for row in rows]
        return sorted(monitors, key=lambda monitor: monitor["name"].lower())

    def list_enabled(self) -> list[dict]:
        return [
            monitor for monitor in self.list_all() if monitor.get("enabled", True)
        ]

    def get_by_id(self, monitor_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM monitors WHERE id = ?",
                (monitor_id,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_monitor(row)

    def create(self, monitor: dict) -> dict:
        normalized = normalize_legacy_source(monitor)
        validate_monitor(normalized)

        if self.get_by_id(normalized["id"]) is not None:
            raise ValueError(f"Monitor already exists: {normalized['id']}")

        now = datetime.now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO monitors (
                    id, config_json, enabled, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    normalized["id"],
                    json.dumps(normalized, ensure_ascii=False),
                    1 if normalized.get("enabled", True) else 0,
                    now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO monitor_execution (
                    monitor_id, execution_status, updated_at
                ) VALUES (?, 'idle', ?)
                """,
                (normalized["id"], now),
            )

        return normalized

    def update(self, monitor_id: str, data: dict) -> dict:
        existing = self.get_by_id(monitor_id)
        if existing is None:
            raise LookupError(f"Monitor not found: {monitor_id}")

        merged = {**existing, **data, "id": monitor_id}
        for key in (
            "execution_status",
            "last_run_at",
            "last_status",
            "last_pages_changed",
            "last_pages_checked",
        ):
            merged.pop(key, None)

        normalized = normalize_legacy_source(merged)
        validate_monitor(normalized)

        now = datetime.now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE monitors
                SET config_json = ?, enabled = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(normalized, ensure_ascii=False),
                    1 if normalized.get("enabled", True) else 0,
                    now,
                    monitor_id,
                ),
            )

        return normalized

    def set_enabled(self, monitor_id: str, enabled: bool) -> dict:
        return self.update(monitor_id, {"enabled": enabled})

    def delete(self, monitor_id: str) -> dict:
        existing = self.get_by_id(monitor_id)
        if existing is None:
            raise LookupError(f"Monitor not found: {monitor_id}")

        with self._connect() as connection:
            connection.execute(
                "DELETE FROM monitor_execution WHERE monitor_id = ?",
                (monitor_id,),
            )
            connection.execute(
                "DELETE FROM monitors WHERE id = ?",
                (monitor_id,),
            )

        return existing

    def get_execution_state(self, monitor_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM monitor_execution WHERE monitor_id = ?",
                (monitor_id,),
            ).fetchone()

        if row is None:
            return None

        return {
            "monitor_id": row["monitor_id"],
            "execution_status": row["execution_status"],
            "last_run_at": row["last_run_at"],
            "last_status": row["last_status"],
            "last_change_status": row["last_change_status"]
            if "last_change_status" in row.keys()
            else row["last_status"],
            "last_pages_changed": row["last_pages_changed"] or 0,
            "last_pages_checked": row["last_pages_checked"] or 0,
            "last_snapshot_id": row["last_snapshot_id"],
            "last_diff_id": row["last_diff_id"],
            "last_error": row["last_error"],
            "last_run_history_id": row["last_run_history_id"],
            "updated_at": row["updated_at"],
        }

    def save_execution_state(
        self,
        monitor_id: str,
        *,
        execution_status: str,
        last_run_at: str | None = None,
        last_change_status: str | None = None,
        last_pages_changed: int = 0,
        last_pages_checked: int = 0,
        last_snapshot_id: int | None = None,
        last_diff_id: int | None = None,
        last_error: str | None = None,
        last_run_history_id: str | None = None,
    ) -> None:
        now = datetime.now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO monitor_execution (
                    monitor_id, execution_status, last_run_at, last_status,
                    last_change_status, last_pages_changed, last_pages_checked,
                    last_snapshot_id, last_diff_id, last_error,
                    last_run_history_id, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(monitor_id) DO UPDATE SET
                    execution_status = excluded.execution_status,
                    last_run_at = excluded.last_run_at,
                    last_status = excluded.last_status,
                    last_change_status = excluded.last_change_status,
                    last_pages_changed = excluded.last_pages_changed,
                    last_pages_checked = excluded.last_pages_checked,
                    last_snapshot_id = excluded.last_snapshot_id,
                    last_diff_id = excluded.last_diff_id,
                    last_error = excluded.last_error,
                    last_run_history_id = excluded.last_run_history_id,
                    updated_at = excluded.updated_at
                """,
                (
                    monitor_id,
                    execution_status,
                    last_run_at,
                    last_change_status,
                    last_change_status,
                    last_pages_changed,
                    last_pages_checked,
                    last_snapshot_id,
                    last_diff_id,
                    last_error,
                    last_run_history_id,
                    now,
                ),
            )

    def list_categories(self) -> list[str]:
        categories: list[str] = []
        seen: set[str] = set()
        for monitor in self.list_all():
            category = monitor.get("category")
            if category is None:
                continue
            cleaned = str(category).strip()
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            categories.append(cleaned)
        return sorted(categories, key=str.lower)

    def get_category_options(self, current: str | None = None) -> list[str]:
        from app.monitors.categories import merge_category_options

        return merge_category_options(
            stored=self.list_categories(),
            current=current,
        )

    # Backward-compatible aliases
    def list_monitors(self) -> list[dict]:
        return self.list_all()

    def get_monitor(self, monitor_id: str) -> dict | None:
        return self.get_by_id(monitor_id)

    def create_monitor(self, monitor: dict) -> dict:
        return self.create(monitor)

    def update_monitor(self, monitor_id: str, updates: dict) -> dict:
        return self.update(monitor_id, updates)

    def delete_monitor(self, monitor_id: str) -> dict:
        return self.delete(monitor_id)


MonitorRepository = SQLiteMonitorRepository

_default_repository: SQLiteMonitorRepository | None = None


def get_monitor_repository(
    db_path: Path | None = None,
    seed_file: Path | None = None,
    sources_file: Path | None = None,
) -> SQLiteMonitorRepository:
    if db_path is not None or seed_file is not None or sources_file is not None:
        return SQLiteMonitorRepository(
            db_path=db_path,
            seed_file=seed_file,
            sources_file=sources_file,
        )

    global _default_repository
    if _default_repository is None:
        _default_repository = SQLiteMonitorRepository()
    return _default_repository


def reset_monitor_repository() -> None:
    global _default_repository
    _default_repository = None


def set_monitor_repository(repository: SQLiteMonitorRepository) -> None:
    global _default_repository
    _default_repository = repository


def log_monitor_repository_state(
    repository: SQLiteMonitorRepository | None = None,
    prefix: str = "",
) -> None:
    repo = repository or get_monitor_repository()
    monitors = repo.list_all()
    enabled_ids = [
        monitor["id"] for monitor in monitors if monitor.get("enabled", True)
    ]
    label = f"{prefix} " if prefix else ""

    logger.info("%sMonitor repository: %s", label.rstrip(), repo.repository_type)
    logger.info("%sMonitor database: %s", label.rstrip(), repo.db_path.resolve())
    logger.info("%sTotal monitors: %s", label.rstrip(), len(monitors))
    logger.info("%sEnabled monitor IDs: %s", label.rstrip(), enabled_ids)
