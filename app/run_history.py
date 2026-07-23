import json
from pathlib import Path

from app.utils.datetime_utils import format_utc_iso, utc_now_iso


RUN_HISTORY_FILE = Path("data/run_history.json")


def _summarize_results(results: list[dict]) -> dict:
    changed_count = 0
    for result in results:
        summary = result.get("page_change_summary") or {}
        page_changes = int(summary.get("pages_changed", 0))
        if page_changes > 0:
            changed_count += page_changes
            continue
        if result.get("diff_id") is not None:
            changed_count += 1

    return {
        "timestamp": utc_now_iso(),
        "total_monitors": len(results),
        "changed_count": changed_count,
        "analyzed_count": sum(
            1 for result in results if result.get("status") == "analyzed"
        ),
        "failed_count": sum(
            1 for result in results if result.get("status") == "error"
        ),
    }


def save_run_history(
    results: list[dict],
    history_file: Path | None = None,
    run_ids: list[int] | None = None,
) -> dict:
    entry = _summarize_results(results)
    history_path = Path(history_file or RUN_HISTORY_FILE)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    if history_path.exists():
        with open(history_path, "r", encoding="utf-8") as file:
            history = json.load(file)
    else:
        history = []

    history.append(entry)
    entry["run_history_id"] = str(len(history))
    if run_ids:
        entry["run_ids"] = run_ids
        if len(run_ids) == 1:
            entry["primary_run_id"] = run_ids[0]

    with open(history_path, "w", encoding="utf-8") as file:
        json.dump(history, file, indent=2, ensure_ascii=False)

    entry["timestamp"] = format_utc_iso(entry["timestamp"]) or entry["timestamp"]
    return entry


def load_run_history(
    history_file: Path = RUN_HISTORY_FILE,
) -> list[dict]:
    history_path = Path(history_file)
    if not history_path.exists():
        return []

    with open(history_path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_latest_run(
    history_file: Path = RUN_HISTORY_FILE,
) -> dict | None:
    history = load_run_history(history_file=history_file)
    if not history:
        return None
    latest = history[-1]
    if latest.get("timestamp"):
        latest = {
            **latest,
            "timestamp": format_utc_iso(latest["timestamp"]) or latest["timestamp"],
        }
    return latest
