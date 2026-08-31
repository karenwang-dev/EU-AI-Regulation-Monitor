from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.utils.datetime_utils import format_utc_iso, get_app_timezone, utc_now_iso

DEFAULT_STATUS_FILE = Path("data/scheduler_status.json")
DEFAULT_LOCK_FILE = Path("data/.scheduler.lock")
HEARTBEAT_STALE_SECONDS = 90
MONITOR_JOB_IDS = ("daily_monitors", "weekly_monitors")
MONITOR_JOB_BY_FREQUENCY = {
    "daily": "daily_monitors",
    "weekly": "weekly_monitors",
}
_pending_job_summaries: dict[str, dict[str, Any]] = {}


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


def attach_job_run_summary(job_name: str, summary: dict[str, Any]) -> None:
    _pending_job_summaries[job_name] = summary


def record_job_start(job_name: str, status_file: Path | None = None) -> None:
    data = _load_status(status_file)
    jobs = data.setdefault("jobs", {})
    now = utc_now_iso()

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
    now = utc_now_iso()
    job = jobs.setdefault(job_name, {})

    job["status"] = "success"
    job["completed_at"] = now
    job["last_error"] = None
    run_summary = _pending_job_summaries.pop(job_name, None)
    if run_summary:
        job["run_summary"] = run_summary
    data["updated_at"] = now
    _save_status(data, status_file)


def record_job_failure(
    job_name: str,
    error: str,
    status_file: Path | None = None,
) -> None:
    data = _load_status(status_file)
    jobs = data.setdefault("jobs", {})
    now = utc_now_iso()
    job = jobs.setdefault(job_name, {})

    job["status"] = "failure"
    job["completed_at"] = now
    job["last_error"] = str(error)
    _pending_job_summaries.pop(job_name, None)
    data["updated_at"] = now
    _save_status(data, status_file)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _seconds_since(timestamp: str | None) -> float | None:
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return None
    now = datetime.now(timezone.utc)
    return (now - parsed.astimezone(timezone.utc)).total_seconds()


def get_scheduler_process_status(status_file: Path | None = None) -> str:
    data = _load_status(status_file)
    process = data.get("process") or {}
    heartbeat_at = process.get("heartbeat_at")
    if not heartbeat_at:
        return "UNKNOWN"

    age = _seconds_since(heartbeat_at)
    if age is None:
        return "UNKNOWN"
    if age <= HEARTBEAT_STALE_SECONDS:
        return "RUNNING"
    return "NOT RUNNING"


def get_scheduler_health_status(status_file: Path | None = None) -> str:
    process_status = get_scheduler_process_status(status_file)
    if process_status == "RUNNING":
        return "running"

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


def _serialize_next_run(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return format_utc_iso(value) or value.isoformat()
    return str(value)


def _collect_next_runs(scheduler) -> dict[str, str | None]:
    next_runs: dict[str, str | None] = {}
    for job in scheduler.get_jobs():
        next_runs[job.id] = _serialize_next_run(getattr(job, "next_run_time", None))
    return next_runs


def record_scheduler_process_start(
    scheduler,
    *,
    status_file: Path | None = None,
) -> None:
    data = _load_status(status_file)
    now = utc_now_iso()
    tz = get_app_timezone()

    data["process"] = {
        "pid": os.getpid(),
        "hostname": socket.gethostname(),
        "started_at": now,
        "heartbeat_at": now,
        "timezone": str(tz),
    }
    data["next_runs"] = _collect_next_runs(scheduler)
    data["updated_at"] = now
    _save_status(data, status_file)


def record_scheduler_heartbeat(
    scheduler,
    *,
    status_file: Path | None = None,
) -> None:
    data = _load_status(status_file)
    process = data.setdefault("process", {})
    now = utc_now_iso()

    process["pid"] = os.getpid()
    process["hostname"] = socket.gethostname()
    process["heartbeat_at"] = now
    if not process.get("started_at"):
        process["started_at"] = now
    if not process.get("timezone"):
        process["timezone"] = str(get_app_timezone())

    data["next_runs"] = _collect_next_runs(scheduler)
    data["updated_at"] = now
    _save_status(data, status_file)


def _pick_latest_monitor_job(jobs: dict[str, dict]) -> dict | None:
    latest_job = None
    latest_timestamp = ""

    for job_name in MONITOR_JOB_IDS:
        job = jobs.get(job_name)
        if not job:
            continue
        timestamp = job.get("completed_at") or job.get("started_at") or ""
        if timestamp >= latest_timestamp:
            latest_timestamp = timestamp
            latest_job = job

    return latest_job


def _derive_last_run_result(job: dict | None) -> str:
    if job is None:
        return "UNKNOWN"

    status = str(job.get("status", "")).lower()
    if status == "running":
        return "UNKNOWN"
    if status == "failure":
        return "FAILED"

    summary = job.get("run_summary") or {}
    failed_count = int(summary.get("failed_count", 0) or 0)
    total_monitors = int(summary.get("total_monitors", 0) or 0)
    changed_count = int(summary.get("changed_count", 0) or 0)
    analyzed_count = int(summary.get("analyzed_count", 0) or 0)

    if status == "success":
        if failed_count > 0 and failed_count >= total_monitors and total_monitors > 0:
            return "FAILED"
        if failed_count > 0:
            return "PARTIAL"
        if changed_count > 0 or analyzed_count > 0:
            return "SUCCESS"
        return "SUCCESS"

    return "UNKNOWN"


def _pick_next_monitor_run(next_runs: dict[str, str | None]) -> str | None:
    candidates: list[tuple[datetime, str]] = []
    for job_name in MONITOR_JOB_IDS:
        timestamp = next_runs.get(job_name)
        parsed = _parse_timestamp(timestamp)
        if parsed is not None:
            candidates.append((parsed, timestamp or ""))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def build_scheduler_dashboard_view(
    *,
    enabled_monitor_count: int,
    status_file: Path | None = None,
) -> dict[str, Any]:
    data = _load_status(status_file)
    jobs = data.get("jobs", {})
    next_runs = data.get("next_runs") or {}
    latest_monitor_job = _pick_latest_monitor_job(jobs)
    run_summary = (latest_monitor_job or {}).get("run_summary") or {}

    return {
        "process_status": get_scheduler_process_status(status_file),
        "process_status_label": get_scheduler_process_status(status_file),
        "last_run_at": (latest_monitor_job or {}).get("completed_at")
        or (latest_monitor_job or {}).get("started_at"),
        "last_run_result": _derive_last_run_result(latest_monitor_job),
        "next_run_at": _pick_next_monitor_run(next_runs),
        "next_runs": next_runs,
        "enabled_monitor_count": enabled_monitor_count,
        "last_run_total_monitors": int(run_summary.get("total_monitors", 0) or 0),
        "last_run_failed_monitors": int(run_summary.get("failed_count", 0) or 0),
        "timezone": (data.get("process") or {}).get("timezone")
        or str(get_app_timezone()),
        "heartbeat_at": (data.get("process") or {}).get("heartbeat_at"),
        "help_text": (
            "The scheduler runs independently from your browser. "
            "Closing this page does not stop scheduled monitoring. "
            "Automatic monitoring requires the scheduler container/process to stay running."
        ),
    }


def acquire_scheduler_lock(lock_file: Path | None = None) -> Path:
    path = lock_file or DEFAULT_LOCK_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        try:
            existing_pid = int(path.read_text(encoding="utf-8").strip())
        except ValueError:
            existing_pid = None

        if existing_pid and _pid_is_running(existing_pid):
            raise RuntimeError(
                f"Scheduler is already running with PID {existing_pid}."
            )
        path.unlink(missing_ok=True)

    path.write_text(str(os.getpid()), encoding="utf-8")
    return path


def release_scheduler_lock(lock_file: Path | None = None) -> None:
    path = lock_file or DEFAULT_LOCK_FILE
    if not path.exists():
        return

    try:
        existing_pid = int(path.read_text(encoding="utf-8").strip())
    except ValueError:
        path.unlink(missing_ok=True)
        return

    if existing_pid == os.getpid():
        path.unlink(missing_ok=True)


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False

    if os.name == "nt":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION,
                False,
                pid,
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True
