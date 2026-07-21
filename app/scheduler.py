from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.logging import get_logger
from app.pipeline import run_pipeline
from app.report.scheduler import generate_weekly_report_job, schedule_weekly_report
from app.run_history import save_run_history
from app.scheduler_status import (
    record_job_failure,
    record_job_start,
    record_job_success,
)
from app.source.source_loader import ALLOWED_FREQUENCIES, load_monitors

logger = get_logger(__name__)


def _run_tracked_job(job_name: str, job_fn):
    record_job_start(job_name)
    try:
        result = job_fn()
        record_job_success(job_name)
        return result
    except Exception as error:
        record_job_failure(job_name, str(error))
        raise


def execute_scheduled_run(frequency: str) -> list[dict]:
    if frequency not in ALLOWED_FREQUENCIES:
        raise ValueError(f"Unsupported frequency: {frequency}")

    logger.info("=" * 60)
    logger.info("Scheduled run started: %s monitors", frequency)
    logger.info("=" * 60)

    results = run_pipeline(frequency=frequency)
    history_entry = save_run_history(results)

    logger.info("Scheduled run completed")
    logger.info(
        "Total=%s Changed=%s Analyzed=%s Failed=%s",
        history_entry["total_monitors"],
        history_entry["changed_count"],
        history_entry["analyzed_count"],
        history_entry["failed_count"],
    )
    logger.info("=" * 60)

    return results


def create_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler()

    scheduler.add_job(
        lambda: _run_tracked_job(
            "daily_monitors",
            lambda: execute_scheduled_run("daily"),
        ),
        CronTrigger(hour=8, minute=0),
        id="daily_monitors",
        name="Daily regulation monitors",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_tracked_job(
            "weekly_monitors",
            lambda: execute_scheduled_run("weekly"),
        ),
        CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="weekly_monitors",
        name="Weekly regulation monitors",
        replace_existing=True,
    )

    schedule_weekly_report(
        scheduler,
        job_fn=lambda: _run_tracked_job(
            "weekly_report_generation",
            generate_weekly_report_job,
        ),
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

    logger.info("=" * 60)
    logger.info("AI Regulation Monitoring Scheduler")
    logger.info("=" * 60)
    logger.info(
        "Configured frequencies: %s",
        ", ".join(sorted(configured_frequencies)),
    )

    for job in scheduler.get_jobs():
        logger.info("- %s: configured trigger=%s", job.id, job.trigger)

    logger.info("Press Ctrl+C to stop.")
    logger.info("=" * 60)

    scheduler.start()
