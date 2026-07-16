import sys

from app.core.logging import get_logger
from app.config.validator import validate_configuration
from app.pipeline import run_pipeline
from app.report.generation import create_and_save_weekly_report
from app.run_history import get_latest_run, save_run_history
from app.scheduler import start_scheduler
from app.source.source_loader import load_monitors

logger = get_logger(__name__)


def _run_startup_validation() -> None:
    result = validate_configuration()
    if result["missing"]:
        logger.warning(
            "Missing required configuration: %s",
            ", ".join(result["missing"]),
        )
    for warning in result["warnings"]:
        logger.warning(warning)
    if result["status"] == "ok":
        logger.info("Configuration validation passed")


def _log_pipeline_summary(results: list[dict]) -> None:
    logger.info("=" * 60)
    logger.info("Pipeline Summary")
    logger.info("=" * 60)

    for result in results:
        logger.info(
            "- %s: %s (snapshot=%s, diff=%s, analysis=%s)",
            result["name"],
            result["status"],
            result["snapshot_id"],
            result.get("diff_id"),
            result.get("analysis_id"),
        )

    logger.info("=" * 60)


def run_once() -> int:
    logger.info("=" * 60)
    logger.info("AI Regulation Monitoring Pipeline")
    logger.info("Running once for all enabled monitors")
    logger.info("=" * 60)

    results = run_pipeline()
    history_entry = save_run_history(results)
    _log_pipeline_summary(results)

    logger.info("Run history saved:")
    logger.info("- Total monitors: %s", history_entry["total_monitors"])
    logger.info("- Changed: %s", history_entry["changed_count"])
    logger.info("- Analyzed: %s", history_entry["analyzed_count"])
    logger.info("- Failed: %s", history_entry["failed_count"])

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
    logger.info("=" * 60)
    logger.info("Weekly Regulation Report Generation")
    logger.info("=" * 60)

    stored_report = create_and_save_weekly_report()

    logger.info("Report saved:")
    logger.info("- ID: %s", stored_report.get("id", "unknown"))
    logger.info("- Generated at: %s", stored_report.get("generated_at", "unknown"))
    logger.info(
        "- Total changes: %s",
        stored_report.get("summary", {}).get("total_changes", 0),
    )
    logger.info(
        "- High risk: %s",
        stored_report.get("summary", {}).get("high_risk", 0),
    )
    logger.info("=" * 60)
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

    if command in {"run-once", "run", "scheduler", "status", "generate-report"}:
        _run_startup_validation()

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
