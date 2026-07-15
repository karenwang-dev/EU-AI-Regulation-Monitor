from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.pipeline import run_pipeline
from app.run_history import save_run_history
from app.source.source_loader import ALLOWED_FREQUENCIES, load_monitors


def execute_scheduled_run(frequency: str) -> list[dict]:
    if frequency not in ALLOWED_FREQUENCIES:
        raise ValueError(f"Unsupported frequency: {frequency}")

    print("=" * 60)
    print(f"Scheduled run started: {frequency} monitors")
    print("=" * 60)

    results = run_pipeline(frequency=frequency)
    history_entry = save_run_history(results)

    print("\n" + "=" * 60)
    print("Scheduled run completed")
    print(
        f"Total={history_entry['total_monitors']} "
        f"Changed={history_entry['changed_count']} "
        f"Analyzed={history_entry['analyzed_count']} "
        f"Failed={history_entry['failed_count']}"
    )
    print("=" * 60)

    return results


def create_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler()

    scheduler.add_job(
        lambda: execute_scheduled_run("daily"),
        CronTrigger(hour=8, minute=0),
        id="daily_monitors",
        name="Daily regulation monitors",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: execute_scheduled_run("weekly"),
        CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="weekly_monitors",
        name="Weekly regulation monitors",
        replace_existing=True,
    )

    return scheduler


def start_scheduler() -> None:
    monitors = load_monitors()
    configured_frequencies = {
        monitor["frequency"]
        for monitor in monitors
        if monitor.get("enabled", True)
    }

    scheduler = create_scheduler()

    print("=" * 60)
    print("AI Regulation Monitoring Scheduler")
    print("=" * 60)
    print("Configured frequencies:", ", ".join(sorted(configured_frequencies)))

    for job in scheduler.get_jobs():
        print(f"- {job.id}: next run at {job.next_run_time}")

    print("Press Ctrl+C to stop.")
    print("=" * 60)

    scheduler.start()
