from apscheduler.events import EVENT_SCHEDULER_STARTED
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.logging import get_logger
from app.core.paths import get_default_monitor_db_path
from app.monitors.repository import get_monitor_repository
from app.monitors.run_persistence import persist_monitor_run
from app.monitors.run_store import get_monitor_run_store
from app.pipeline import run_pipeline
from app.report.scheduler import generate_weekly_report_job, schedule_weekly_report
from app.run_history import save_run_history
from app.scheduler_status import (
    MONITOR_JOB_BY_FREQUENCY,
    acquire_scheduler_lock,
    attach_job_run_summary,
    record_job_failure,
    record_job_start,
    record_job_success,
    record_scheduler_heartbeat,
    record_scheduler_process_start,
    release_scheduler_lock,
)
from app.source.source_loader import ALLOWED_FREQUENCIES, load_monitors
from app.utils.datetime_utils import get_app_timezone, utc_now

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

    batch_started = utc_now()
    results = run_pipeline(frequency=frequency)
    batch_finished = utc_now()

    repository = get_monitor_repository()
    run_store = get_monitor_run_store(db_path=get_default_monitor_db_path())
    monitor_map = {
        monitor["id"]: monitor
        for monitor in load_monitors(repository=repository)
        if monitor.get("frequency") == frequency
    }
    run_ids: list[int] = []

    for result in results:
        monitor_id = result.get("source_id")
        monitor = monitor_map.get(monitor_id)
        if monitor is None:
            continue
        run_id = persist_monitor_run(
            repository=repository,
            run_store=run_store,
            monitor=monitor,
            pipeline_result=result,
            triggered_by="scheduler",
            started_at=batch_started,
            finished_at=batch_finished,
        )
        if run_id is not None:
            run_ids.append(run_id)

    history_entry = save_run_history(results, run_ids=run_ids or None)
    attach_job_run_summary(
        MONITOR_JOB_BY_FREQUENCY[frequency],
        history_entry,
    )

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
    tz = get_app_timezone()
    scheduler = BlockingScheduler(timezone=tz)

    scheduler.add_job(
        lambda: _run_tracked_job(
            "daily_monitors",
            lambda: execute_scheduled_run("daily"),
        ),
        CronTrigger(hour=8, minute=0, timezone=tz),
        id="daily_monitors",
        name="Daily regulation monitors",
        replace_existing=True,
    )
    scheduler.add_job(
        lambda: _run_tracked_job(
            "weekly_monitors",
            lambda: execute_scheduled_run("weekly"),
        ),
        CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=tz),
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
        timezone=tz,
    )

    return scheduler


def _register_scheduler_observability(scheduler: BlockingScheduler) -> None:
    def on_scheduler_started(event) -> None:
        if event.code != EVENT_SCHEDULER_STARTED:
            return
        record_scheduler_process_start(scheduler)
        for job in scheduler.get_jobs():
            next_run = getattr(job, "next_run_time", None)
            logger.info(
                "- %s: configured trigger=%s next_run=%s",
                job.id,
                job.trigger,
                next_run,
            )

    scheduler.add_listener(on_scheduler_started, EVENT_SCHEDULER_STARTED)
    scheduler.add_job(
        lambda: record_scheduler_heartbeat(scheduler),
        IntervalTrigger(seconds=60),
        id="scheduler_heartbeat",
        name="Scheduler heartbeat",
        replace_existing=True,
    )


def start_scheduler() -> None:
    monitors = load_monitors()
    configured_frequencies = {
        monitor["frequency"]
        for monitor in monitors
        if monitor.get("enabled", True)
    }

    lock_path = acquire_scheduler_lock()
    scheduler = create_scheduler()
    tz = get_app_timezone()
    _register_scheduler_observability(scheduler)

    logger.info("=" * 60)
    logger.info("AI Regulation Monitoring Scheduler")
    logger.info("=" * 60)
    logger.info("Scheduler timezone: %s", tz)
    logger.info(
        "Configured frequencies: %s",
        ", ".join(sorted(configured_frequencies)),
    )
    logger.info("Scheduler lock acquired: %s", lock_path)
    logger.info("Press Ctrl+C to stop.")
    logger.info("=" * 60)

    try:
        scheduler.start()
    finally:
        release_scheduler_lock()
