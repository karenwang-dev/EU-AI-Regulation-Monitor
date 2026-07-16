from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

DEFAULT_STATUS_FILE = Path("data/scheduler_status.json")


def _resolve_status_file(status_file: Path | None) -> Path:
    return status_file or DEFAULT_STATUS_FILE


def _load_status(status_file: Path | None = None) -> dict:
    path = _resolve_status_file(status_file)
    if not path.exists():
        return {"jobs": {}}

    return json.loads(path.read_text(encoding="utf-8"))


def _save_status(data: dict, status_file: Path | None = None) -> None:
    path = _resolve_status_file(status_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_job_start(job_name: str, status_file: Path | None = None) -> None:
    data = _load_status(status_file)
    jobs = data.setdefault("jobs", {})
    now = datetime.now().isoformat(timespec="seconds")

    jobs[job_name] = {
        "status": "running",
        "started_at": now,
        "completed_at": None,
        "last_error": None,
    }
    data["updated_at"] = now
    _save_status(data, status_file)


def record_job_success(job_name: str, status_file: Path | None = None) -> None:
    data = _load_status(status_file)
    jobs = data.setdefault("jobs", {})
    now = datetime.now().isoformat(timespec="seconds")
    job = jobs.setdefault(job_name, {})

    job["status"] = "success"
    job["completed_at"] = now
    job["last_error"] = None
    data["updated_at"] = now
    _save_status(data, status_file)


def record_job_failure(
    job_name: str,
    error: str,
    status_file: Path | None = None,
) -> None:
    data = _load_status(status_file)
    jobs = data.setdefault("jobs", {})
    now = datetime.now().isoformat(timespec="seconds")
    job = jobs.setdefault(job_name, {})

    job["status"] = "failure"
    job["completed_at"] = now
    job["last_error"] = str(error)
    data["updated_at"] = now
    _save_status(data, status_file)


def get_scheduler_health_status(status_file: Path | None = None) -> str:
    data = _load_status(status_file)
    jobs = data.get("jobs", {})
    if not jobs:
        return "unknown"

    if any(job.get("status") == "running" for job in jobs.values()):
        return "running"

    latest_job = None
    latest_timestamp = ""

    for job in jobs.values():
        timestamp = job.get("completed_at") or job.get("started_at") or ""
        if timestamp >= latest_timestamp:
            latest_timestamp = timestamp
            latest_job = job

    if latest_job is None:
        return "unknown"

    status = latest_job.get("status")
    if status == "success":
        return "ok"
    if status == "failure":
        return "error"

    return "unknown"
