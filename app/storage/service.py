import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path


RAW_DIR = Path("data/raw")
META_FILE = Path("data/metadata/snapshots.json")
DB_PATH = Path("data/storage.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL,
    file_path TEXT NOT NULL,
    hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_source_id
    ON snapshots(source_id);

CREATE INDEX IF NOT EXISTS idx_snapshots_source_timestamp
    ON snapshots(source_id, timestamp);

CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_analyses_snapshot_id
    ON analyses(snapshot_id);

CREATE INDEX IF NOT EXISTS idx_analyses_source_id
    ON analyses(source_id);

CREATE TABLE IF NOT EXISTS diffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    old_snapshot_id INTEGER,
    new_snapshot_id INTEGER NOT NULL,
    changed INTEGER NOT NULL,
    added_content_json TEXT NOT NULL,
    removed_content_json TEXT NOT NULL,
    diff_text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (old_snapshot_id) REFERENCES snapshots(id),
    FOREIGN KEY (new_snapshot_id) REFERENCES snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_diffs_source_id
    ON diffs(source_id);

CREATE INDEX IF NOT EXISTS idx_diffs_new_snapshot_id
    ON diffs(new_snapshot_id);

CREATE TABLE IF NOT EXISTS crawl_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    last_snapshot_id INTEGER NOT NULL,
    last_hash TEXT NOT NULL,
    last_crawled_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (last_snapshot_id) REFERENCES snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_crawl_cache_url
    ON crawl_cache(url);

CREATE TABLE IF NOT EXISTS knowledge_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER,
    source_id TEXT,
    title TEXT,
    category TEXT,
    regulation_type TEXT,
    summary TEXT,
    effective_date TEXT,
    countries_json TEXT,
    products_json TEXT,
    modules_json TEXT,
    requirements_json TEXT,
    actions_json TEXT,
    confidence TEXT,
    created_at TEXT,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_items_source_id
    ON knowledge_items(source_id);

CREATE INDEX IF NOT EXISTS idx_knowledge_items_category
    ON knowledge_items(category);

CREATE INDEX IF NOT EXISTS idx_knowledge_items_created_at
    ON knowledge_items(created_at);
"""


def calculate_hash(content: str) -> str:
    return hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()


class StorageService:

    def __init__(
        self,
        db_path: Path = DB_PATH,
        raw_dir: Path = RAW_DIR,
        meta_file: Path = META_FILE,
    ):
        self.db_path = Path(db_path)
        self.raw_dir = Path(raw_dir)
        self.meta_file = Path(meta_file)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            count = connection.execute(
                "SELECT COUNT(*) FROM snapshots"
            ).fetchone()[0]
            if count == 0:
                self._import_legacy_snapshots(connection)

    def _import_legacy_snapshots(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        if not self.meta_file.exists():
            return

        with open(self.meta_file, "r", encoding="utf-8") as file:
            records = json.load(file)

        for record in records:
            if self._snapshot_exists(
                connection,
                record["source_id"],
                record["timestamp"],
                record["hash"],
            ):
                continue

            connection.execute(
                """
                INSERT INTO snapshots (
                    source_id, url, title, timestamp,
                    file_path, hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record["source_id"],
                    record["url"],
                    record.get("title", ""),
                    record["timestamp"],
                    record["file"],
                    record["hash"],
                    record["timestamp"],
                ),
            )

    def _snapshot_exists(
        self,
        connection: sqlite3.Connection,
        source_id: str,
        timestamp: str,
        content_hash: str,
    ) -> bool:
        row = connection.execute(
            """
            SELECT 1 FROM snapshots
            WHERE source_id = ? AND timestamp = ? AND hash = ?
            """,
            (source_id, timestamp, content_hash),
        ).fetchone()
        return row is not None

    def _row_to_snapshot(self, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "source_id": row["source_id"],
            "url": row["url"],
            "title": row["title"],
            "timestamp": row["timestamp"],
            "file_path": row["file_path"],
            "hash": row["hash"],
        }

    def _write_markdown_file(
        self,
        source_id: str,
        markdown: str,
        captured_at: datetime,
        url_slug: str | None = None,
    ) -> Path:
        date_folder = captured_at.strftime("%Y-%m-%d")
        time_suffix = captured_at.strftime("%H%M%S")
        folder = self.raw_dir / date_folder
        folder.mkdir(parents=True, exist_ok=True)
        suffix = f"_{url_slug}" if url_slug else ""
        file_path = folder / f"{source_id}{suffix}_{time_suffix}.md"
        file_path.write_text(markdown, encoding="utf-8")
        return file_path

    def _append_legacy_metadata(self, snapshot: dict) -> None:
        self.meta_file.parent.mkdir(parents=True, exist_ok=True)

        if self.meta_file.exists():
            with open(self.meta_file, "r", encoding="utf-8") as file:
                data = json.load(file)
        else:
            data = []

        data.append(
            {
                "source_id": snapshot["source_id"],
                "url": snapshot["url"],
                "timestamp": snapshot["timestamp"],
                "file": snapshot["file_path"],
                "hash": snapshot["hash"],
            }
        )

        with open(self.meta_file, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)

    def save_snapshot(self, crawl_result: dict) -> dict:
        captured_at = datetime.fromisoformat(crawl_result["timestamp"])
        markdown = crawl_result["markdown"]
        content_hash = calculate_hash(markdown)
        file_path = self._write_markdown_file(
            crawl_result["source_id"],
            markdown,
            captured_at,
            url_slug=crawl_result.get("url_slug"),
        )

        snapshot = {
            "source_id": crawl_result["source_id"],
            "url": crawl_result["url"],
            "title": crawl_result.get("title", ""),
            "timestamp": crawl_result["timestamp"],
            "file_path": str(file_path),
            "hash": content_hash,
            "normalized_url": crawl_result.get("normalized_url", crawl_result["url"]),
            "crawl_depth": crawl_result.get("crawl_depth", 0),
            "parent_url": crawl_result.get("parent_url"),
            "cleaned_content": markdown,
        }

        with self._connect() as connection:
            if self._snapshot_exists(
                connection,
                snapshot["source_id"],
                snapshot["timestamp"],
                snapshot["hash"],
            ):
                row = connection.execute(
                    """
                    SELECT * FROM snapshots
                    WHERE source_id = ? AND timestamp = ? AND hash = ?
                    """,
                    (
                        snapshot["source_id"],
                        snapshot["timestamp"],
                        snapshot["hash"],
                    ),
                ).fetchone()
                return self._row_to_snapshot(row)

            cursor = connection.execute(
                """
                INSERT INTO snapshots (
                    source_id, url, title, timestamp,
                    file_path, hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot["source_id"],
                    snapshot["url"],
                    snapshot["title"],
                    snapshot["timestamp"],
                    snapshot["file_path"],
                    snapshot["hash"],
                    snapshot["timestamp"],
                ),
            )
            snapshot["id"] = cursor.lastrowid

        self._append_legacy_metadata(snapshot)
        return snapshot

    def get_latest_snapshot(self, source_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM snapshots
                WHERE source_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (source_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_snapshot(row)

    def get_distinct_monitor_urls(self, source_id: str) -> set[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT DISTINCT url FROM snapshots
                WHERE source_id = ?
                """,
                (source_id,),
            ).fetchall()
        return {row["url"] for row in rows}

    def get_snapshot_by_id(self, snapshot_id: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM snapshots WHERE id = ?",
                (snapshot_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_snapshot(row)

    def get_crawl_cache(self, url: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM crawl_cache WHERE url = ?",
                (url,),
            ).fetchone()

        if row is None:
            return None

        return {
            "id": row["id"],
            "url": row["url"],
            "last_snapshot_id": row["last_snapshot_id"],
            "last_hash": row["last_hash"],
            "last_crawled_at": row["last_crawled_at"],
            "created_at": row["created_at"],
        }

    def update_crawl_cache(
        self,
        url: str,
        snapshot_id: int,
        content_hash: str,
    ) -> dict:
        now = datetime.now().isoformat()

        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id FROM crawl_cache WHERE url = ?",
                (url,),
            ).fetchone()

            if existing is None:
                connection.execute(
                    """
                    INSERT INTO crawl_cache (
                        url,
                        last_snapshot_id,
                        last_hash,
                        last_crawled_at,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (url, snapshot_id, content_hash, now, now),
                )
            else:
                connection.execute(
                    """
                    UPDATE crawl_cache
                    SET last_snapshot_id = ?,
                        last_hash = ?,
                        last_crawled_at = ?
                    WHERE url = ?
                    """,
                    (snapshot_id, content_hash, now, url),
                )

        cache_entry = self.get_crawl_cache(url)
        if cache_entry is None:
            raise ValueError(f"Failed to update crawl cache for URL: {url}")
        return cache_entry

    def save_analysis(self, snapshot_id: int, analysis: dict) -> dict:
        with self._connect() as connection:
            snapshot = connection.execute(
                "SELECT source_id FROM snapshots WHERE id = ?",
                (snapshot_id,),
            ).fetchone()

            if snapshot is None:
                raise ValueError(f"Snapshot not found: {snapshot_id}")

            created_at = datetime.now().isoformat()
            cursor = connection.execute(
                """
                INSERT INTO analyses (
                    snapshot_id, source_id, analysis_json, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    snapshot["source_id"],
                    json.dumps(analysis, ensure_ascii=False),
                    created_at,
                ),
            )

            return {
                "id": cursor.lastrowid,
                "snapshot_id": snapshot_id,
                "source_id": snapshot["source_id"],
                "analysis": analysis,
                "created_at": created_at,
            }

    def get_analysis_history(self, source_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    analyses.id,
                    analyses.snapshot_id,
                    analyses.source_id,
                    analyses.analysis_json,
                    analyses.created_at,
                    snapshots.timestamp AS snapshot_timestamp
                FROM analyses
                JOIN snapshots ON snapshots.id = analyses.snapshot_id
                WHERE analyses.source_id = ?
                ORDER BY analyses.created_at DESC
                """,
                (source_id,),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "snapshot_id": row["snapshot_id"],
                "source_id": row["source_id"],
                "analysis": json.loads(row["analysis_json"]),
                "created_at": row["created_at"],
                "snapshot_timestamp": row["snapshot_timestamp"],
            }
            for row in rows
        ]

    def save_diff(self, diff_result: dict) -> dict:
        created_at = datetime.now().isoformat()

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO diffs (
                    source_id,
                    old_snapshot_id,
                    new_snapshot_id,
                    changed,
                    added_content_json,
                    removed_content_json,
                    diff_text,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    diff_result["source_id"],
                    diff_result["old_snapshot_id"],
                    diff_result["new_snapshot_id"],
                    int(diff_result["changed"]),
                    json.dumps(
                        diff_result["added_content"],
                        ensure_ascii=False,
                    ),
                    json.dumps(
                        diff_result["removed_content"],
                        ensure_ascii=False,
                    ),
                    diff_result["diff_text"],
                    created_at,
                ),
            )

            return {
                "id": cursor.lastrowid,
                **diff_result,
                "created_at": created_at,
            }

    def get_diff_history(self, source_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    source_id,
                    old_snapshot_id,
                    new_snapshot_id,
                    changed,
                    added_content_json,
                    removed_content_json,
                    diff_text,
                    created_at
                FROM diffs
                WHERE source_id = ?
                ORDER BY created_at DESC
                """,
                (source_id,),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "source_id": row["source_id"],
                "old_snapshot_id": row["old_snapshot_id"],
                "new_snapshot_id": row["new_snapshot_id"],
                "changed": bool(row["changed"]),
                "added_content": json.loads(row["added_content_json"]),
                "removed_content": json.loads(row["removed_content_json"]),
                "diff_text": row["diff_text"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def _serialize_json_list(self, values) -> str:
        if values is None:
            return json.dumps([], ensure_ascii=False)
        return json.dumps(values, ensure_ascii=False)

    def _deserialize_json_list(self, value: str | None) -> list:
        if not value:
            return []
        return json.loads(value)

    def _serialize_actions_payload(self, item: dict) -> str:
        actions = item.get("actions", [])
        relationships = item.get("relationships", [])
        if relationships:
            payload = {
                "actions": actions,
                "relationships": relationships,
            }
            return json.dumps(payload, ensure_ascii=False)
        return json.dumps(actions, ensure_ascii=False)

    def _deserialize_actions_payload(
        self,
        value: str | None,
    ) -> tuple[list, list]:
        if not value:
            return [], []
        data = json.loads(value)
        if isinstance(data, dict):
            return (
                list(data.get("actions", [])),
                list(data.get("relationships", [])),
            )
        if isinstance(data, list):
            return data, []
        return [], []

    def _row_to_knowledge_item(
        self,
        row: sqlite3.Row,
        *,
        list_only: bool = False,
    ) -> dict:
        modules = self._deserialize_json_list(row["modules_json"])
        actions, relationships = self._deserialize_actions_payload(
            row["actions_json"]
        )
        if list_only:
            return {
                "id": row["id"],
                "title": row["title"],
                "category": row["category"],
                "modules": modules,
            }

        return {
            "id": row["id"],
            "snapshot_id": row["snapshot_id"],
            "source_id": row["source_id"],
            "title": row["title"],
            "category": row["category"],
            "regulation_type": row["regulation_type"],
            "summary": row["summary"],
            "effective_date": row["effective_date"],
            "countries": self._deserialize_json_list(row["countries_json"]),
            "products": self._deserialize_json_list(row["products_json"]),
            "modules": modules,
            "requirements": self._deserialize_json_list(
                row["requirements_json"]
            ),
            "actions": actions,
            "relationships": relationships,
            "confidence": row["confidence"],
            "created_at": row["created_at"],
        }

    def save_knowledge_item(self, item: dict) -> dict:
        created_at = datetime.now().isoformat()
        countries = item.get("countries", [])
        products = item.get("products", [])
        modules = item.get("modules", [])
        requirements = item.get("requirements", [])
        actions_payload = self._serialize_actions_payload(item)

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO knowledge_items (
                    snapshot_id,
                    source_id,
                    title,
                    category,
                    regulation_type,
                    summary,
                    effective_date,
                    countries_json,
                    products_json,
                    modules_json,
                    requirements_json,
                    actions_json,
                    confidence,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.get("snapshot_id"),
                    item.get("source_id", ""),
                    item.get("title", ""),
                    item.get("category", ""),
                    item.get("regulation_type", ""),
                    item.get("summary", ""),
                    item.get("effective_date", ""),
                    self._serialize_json_list(countries),
                    self._serialize_json_list(products),
                    self._serialize_json_list(modules),
                    self._serialize_json_list(requirements),
                    actions_payload,
                    item.get("confidence", ""),
                    created_at,
                ),
            )
            item_id = cursor.lastrowid
            row = connection.execute(
                "SELECT * FROM knowledge_items WHERE id = ?",
                (item_id,),
            ).fetchone()

        if row is None:
            raise ValueError(f"Failed to save knowledge item: {item_id}")

        return self._row_to_knowledge_item(row)

    def get_knowledge_item(self, item_id: int) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_items WHERE id = ?",
                (item_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_knowledge_item(row)

    def get_knowledge_items(
        self,
        category: str | None = None,
        module: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        query = "SELECT * FROM knowledge_items WHERE 1=1"
        params: list = []

        if category is not None:
            query += " AND category = ?"
            params.append(category)

        if module is not None:
            query += " AND modules_json LIKE ?"
            params.append(f'%"{module}"%')

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [
            self._row_to_knowledge_item(row, list_only=True)
            for row in rows
        ]

    def search_knowledge(
        self,
        query: str,
        limit: int = 50,
    ) -> list[dict]:
        pattern = f"%{query}%"

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM knowledge_items
                WHERE title LIKE ?
                   OR summary LIKE ?
                   OR requirements_json LIKE ?
                   OR modules_json LIKE ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, pattern, limit),
            ).fetchall()

        return [
            self._row_to_knowledge_item(row, list_only=True)
            for row in rows
        ]


_default_service: StorageService | None = None


def _get_service() -> StorageService:
    global _default_service
    if _default_service is None:
        from app.core.paths import PROJECT_ROOT

        _default_service = StorageService(
            db_path=(PROJECT_ROOT / DB_PATH).resolve(),
            raw_dir=(PROJECT_ROOT / RAW_DIR).resolve(),
            meta_file=(PROJECT_ROOT / META_FILE).resolve(),
        )
    return _default_service


def save_snapshot(crawl_result: dict) -> dict:
    return _get_service().save_snapshot(crawl_result)


def get_latest_snapshot(source_id: str) -> dict | None:
    return _get_service().get_latest_snapshot(source_id)


def get_snapshot_by_id(snapshot_id: int) -> dict | None:
    return _get_service().get_snapshot_by_id(snapshot_id)


def get_crawl_cache(url: str) -> dict | None:
    return _get_service().get_crawl_cache(url)


def update_crawl_cache(
    url: str,
    snapshot_id: int,
    content_hash: str,
) -> dict:
    return _get_service().update_crawl_cache(url, snapshot_id, content_hash)


def save_analysis(snapshot_id: int, analysis: dict) -> dict:
    return _get_service().save_analysis(snapshot_id, analysis)


def get_analysis_history(source_id: str) -> list[dict]:
    return _get_service().get_analysis_history(source_id)


def save_diff(diff_result: dict) -> dict:
    return _get_service().save_diff(diff_result)


def get_diff_history(source_id: str) -> list[dict]:
    return _get_service().get_diff_history(source_id)


def save_knowledge_item(item: dict) -> dict:
    return _get_service().save_knowledge_item(item)


def get_knowledge_item(item_id: int) -> dict | None:
    return _get_service().get_knowledge_item(item_id)


def get_knowledge_items(
    category: str | None = None,
    module: str | None = None,
    limit: int = 50,
) -> list[dict]:
    return _get_service().get_knowledge_items(
        category=category,
        module=module,
        limit=limit,
    )


def search_knowledge(query: str, limit: int = 50) -> list[dict]:
    return _get_service().search_knowledge(query, limit=limit)
