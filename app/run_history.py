import json
from datetime import datetime
from pathlib import Path


RUN_HISTORY_FILE = Path("data/run_history.json")


def _summarize_results(results: list[dict]) -> dict:
    return {
        "timestamp": datetime.now().isoformat(),
        "total_monitors": len(results),
        "changed_count": sum(
            1 for result in results if result.get("diff_id") is not None
        ),
        "analyzed_count": sum(
            1 for result in results if result.get("status") == "analyzed"
        ),
        "failed_count": sum(
            1 for result in results if result.get("status") == "error"
        ),
    }


def save_run_history(
    results: list[dict],
    history_file: Path = RUN_HISTORY_FILE,
) -> dict:
    entry = _summarize_results(results)
    history_path = Path(history_file)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    if history_path.exists():
        with open(history_path, "r", encoding="utf-8") as file:
            history = json.load(file)
    else:
        history = []

    history.append(entry)

    with open(history_path, "w", encoding="utf-8") as file:
        json.dump(history, file, indent=2, ensure_ascii=False)

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
    return history[-1]
