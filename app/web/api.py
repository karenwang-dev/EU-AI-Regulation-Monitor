import json
from pathlib import Path

from fastapi import FastAPI, HTTPException

from app.run_history import get_latest_run
from app.source.source_loader import load_monitors
from app.storage.service import StorageService, _get_service


def _build_change_summary(diff: dict) -> str:
    added = diff.get("added_content", [])
    removed = diff.get("removed_content", [])

    parts = []
    if added:
        preview = "; ".join(added[:3])
        parts.append(f"Added {len(added)} line(s): {preview}")
    if removed:
        preview = "; ".join(removed[:3])
        parts.append(f"Removed {len(removed)} line(s): {preview}")

    if parts:
        return " | ".join(parts)

    return "No content changes detected."


def _get_analysis_by_id(
    storage: StorageService,
    analysis_id: int,
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
            WHERE id = ?
            """,
            (analysis_id,),
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


def _get_diff_by_id(
    storage: StorageService,
    diff_id: int,
) -> dict | None:
    with storage._connect() as connection:
        row = connection.execute(
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
            WHERE id = ?
            """,
            (diff_id,),
        ).fetchone()

    if row is None:
        return None

    return {
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


def _get_latest_changes(
    storage: StorageService,
    limit: int = 50,
) -> list[dict]:
    monitors = load_monitors()
    all_diffs = []

    for monitor in monitors:
        diffs = storage.get_diff_history(monitor["id"])
        all_diffs.extend(diffs)

    all_diffs.sort(key=lambda item: item["created_at"], reverse=True)

    return [
        {
            "id": diff["id"],
            "source_id": diff["source_id"],
            "timestamp": diff["created_at"],
            "changed_content_summary": _build_change_summary(diff),
        }
        for diff in all_diffs[:limit]
    ]


def create_app(
    storage_service: StorageService | None = None,
    history_file: Path | None = None,
) -> FastAPI:
    storage = storage_service or _get_service()
    app = FastAPI(title="AI Regulation Monitor API")

    @app.get("/")
    def root_status():
        return {
            "status": "ok",
            "service": "AI Regulation Monitor API",
        }

    @app.get("/api/status")
    def api_status():
        latest_run = get_latest_run(
            history_file=history_file
        ) if history_file else get_latest_run()
        monitors = load_monitors()

        return {
            "last_run": latest_run,
            "monitor_count": len(monitors),
            "changed_count": latest_run.get("changed_count", 0)
            if latest_run
            else 0,
            "analyzed_count": latest_run.get("analyzed_count", 0)
            if latest_run
            else 0,
            "failed_count": latest_run.get("failed_count", 0)
            if latest_run
            else 0,
        }

    @app.get("/api/monitors")
    def api_monitors():
        monitors = load_monitors()
        return {"monitors": monitors}

    @app.get("/api/changes")
    def api_changes():
        return {"changes": _get_latest_changes(storage)}

    @app.get("/api/analysis/{analysis_id}")
    def api_analysis(analysis_id: int):
        analysis = _get_analysis_by_id(storage, analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return analysis

    @app.get("/api/diff/{diff_id}")
    def api_diff(diff_id: int):
        diff = _get_diff_by_id(storage, diff_id)
        if diff is None:
            raise HTTPException(status_code=404, detail="Diff not found")
        return diff

    return app


app = create_app()
