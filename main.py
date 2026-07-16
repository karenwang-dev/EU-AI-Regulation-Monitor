import sys

from app.pipeline import run_pipeline
from app.report.generation import create_and_save_weekly_report
from app.run_history import get_latest_run, save_run_history
from app.scheduler import start_scheduler
from app.source.source_loader import load_monitors


def _print_pipeline_summary(results: list[dict]) -> None:
    print("\n" + "=" * 60)
    print("Pipeline Summary")
    print("=" * 60)

    for result in results:
        print(
            f"- {result['name']}: {result['status']} "
            f"(snapshot={result['snapshot_id']}, "
            f"diff={result.get('diff_id')}, "
            f"analysis={result.get('analysis_id')})"
        )

    print("=" * 60)


def run_once() -> int:
    print("=" * 60)
    print("AI Regulation Monitoring Pipeline")
    print("Running once for all enabled monitors")
    print("=" * 60)

    results = run_pipeline()
    history_entry = save_run_history(results)
    _print_pipeline_summary(results)

    print("\nRun history saved:")
    print(f"- Total monitors: {history_entry['total_monitors']}")
    print(f"- Changed: {history_entry['changed_count']}")
    print(f"- Analyzed: {history_entry['analyzed_count']}")
    print(f"- Failed: {history_entry['failed_count']}")

    return 0


def show_status() -> int:
    monitors = load_monitors()
    enabled_monitors = [
        monitor for monitor in monitors if monitor.get("enabled", True)
    ]
    latest_run = get_latest_run()

    print("=" * 60)
    print("AI Regulation Monitoring Status")
    print("=" * 60)
    print(f"Configured monitors: {len(monitors)}")
    print(f"Enabled monitors: {len(enabled_monitors)}")

    daily_count = sum(
        1 for monitor in enabled_monitors if monitor["frequency"] == "daily"
    )
    weekly_count = sum(
        1 for monitor in enabled_monitors if monitor["frequency"] == "weekly"
    )
    print(f"Daily monitors: {daily_count}")
    print(f"Weekly monitors: {weekly_count}")

    if latest_run is None:
        print("\nLast run: none")
    else:
        print("\nLast run:")
        print(f"- Timestamp: {latest_run['timestamp']}")
        print(f"- Total monitors: {latest_run['total_monitors']}")
        print(f"- Changed: {latest_run['changed_count']}")
        print(f"- Analyzed: {latest_run['analyzed_count']}")
        print(f"- Failed: {latest_run['failed_count']}")

    print("=" * 60)
    return 0


def generate_report() -> int:
    print("=" * 60)
    print("Weekly Regulation Report Generation")
    print("=" * 60)

    stored_report = create_and_save_weekly_report()

    print("\nReport saved:")
    print(f"- ID: {stored_report.get('id', 'unknown')}")
    print(f"- Generated at: {stored_report.get('generated_at', 'unknown')}")
    print(
        "- Total changes: "
        f"{stored_report.get('summary', {}).get('total_changes', 0)}"
    )
    print(
        "- High risk: "
        f"{stored_report.get('summary', {}).get('high_risk', 0)}"
    )
    print("=" * 60)
    return 0


def print_usage() -> None:
    print("Usage:")
    print("  python main.py run-once")
    print("  python main.py scheduler")
    print("  python main.py status")
    print("  python main.py generate-report")
    print("  python main.py run")


def main() -> int:
    if len(sys.argv) < 2:
        print_usage()
        return 1

    command = sys.argv[1]

    if command == "run-once" or command == "run":
        return run_once()

    if command == "scheduler":
        start_scheduler()
        return 0

    if command == "status":
        return show_status()

    if command == "generate-report":
        return generate_report()

    print_usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
