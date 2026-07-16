from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

DEFAULT_REPORTS_DIR = Path("data/reports")


def _get_reports_dir(reports_dir: Path | str | None = None) -> Path:
    directory = Path(reports_dir) if reports_dir is not None else DEFAULT_REPORTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _report_id_from_filename(filename: str) -> str:
    if filename.endswith(".json"):
        return filename[:-5]
    return filename


def _extract_generated_date(generated_at: str) -> str:
    cleaned = str(generated_at or "").strip()
    if len(cleaned) >= 10:
        return cleaned[:10]
    return datetime.now().date().isoformat()


def _build_filename(generated_at: str, reports_dir: Path) -> str:
    date_part = _extract_generated_date(generated_at)
    base_name = f"{date_part}_weekly_report"
    filename = f"{base_name}.json"
    if not (reports_dir / filename).exists():
        return filename

    counter = 2
    while (reports_dir / f"{base_name}_{counter}.json").exists():
        counter += 1
    return f"{base_name}_{counter}.json"


def save_report(
    report: dict,
    reports_dir: Path | str | None = None,
) -> dict:
    directory = _get_reports_dir(reports_dir)
    generated_at = str(report.get("generated_at") or datetime.now().isoformat())
    filename = _build_filename(generated_at, directory)
    report_id = _report_id_from_filename(filename)

    stored_report = {
        **report,
        "id": report_id,
        "filename": filename,
        "generated_at": generated_at,
    }

    path = directory / filename
    path.write_text(
        json.dumps(stored_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return stored_report


def get_report_history(
    limit: int = 20,
    reports_dir: Path | str | None = None,
) -> list[dict]:
    directory = _get_reports_dir(reports_dir)
    reports: list[dict] = []

    for path in sorted(directory.glob("*_weekly_report*.json"), reverse=True):
        report = _load_report_file(path)
        if report is not None:
            reports.append(report)
        if len(reports) >= limit:
            break

    reports.sort(
        key=lambda item: item.get("generated_at", ""),
        reverse=True,
    )
    return reports[:limit]


def get_latest_report(
    reports_dir: Path | str | None = None,
) -> dict | None:
    history = get_report_history(limit=1, reports_dir=reports_dir)
    return history[0] if history else None


def get_report(
    report_id: str,
    reports_dir: Path | str | None = None,
) -> dict | None:
    directory = _get_reports_dir(reports_dir)
    direct_path = directory / f"{report_id}.json"
    if direct_path.exists():
        return _load_report_file(direct_path)

    for path in directory.glob("*_weekly_report*.json"):
        if _report_id_from_filename(path.name) == report_id:
            return _load_report_file(path)

    return None


def _load_report_file(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(data, dict):
        return None

    if "id" not in data:
        data["id"] = _report_id_from_filename(path.name)
    if "filename" not in data:
        data["filename"] = path.name
    return data
