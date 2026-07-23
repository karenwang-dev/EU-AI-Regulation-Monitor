from __future__ import annotations

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from app.core.logging import get_logger
from app.report.config import load_report_config, normalize_report_config
from app.utils.datetime_utils import get_app_timezone

logger = get_logger(__name__)


def generate_weekly_report_job(
    *,
    create_and_save_weekly_report_fn=None,
) -> dict:
    if create_and_save_weekly_report_fn is None:
        from app.report.generation import create_and_save_weekly_report

        create_and_save_weekly_report_fn = create_and_save_weekly_report

    logger.info("=" * 60)
    logger.info("Weekly report generation started")
    logger.info("=" * 60)

    stored_report = create_and_save_weekly_report_fn()

    logger.info("Weekly report generation completed")
    logger.info("Report ID: %s", stored_report.get("id", "unknown"))
    logger.info(
        "Total changes: %s",
        stored_report.get("summary", {}).get("total_changes", 0),
    )
    logger.info("=" * 60)

    return stored_report


def schedule_weekly_report(
    scheduler: BaseScheduler,
    config: dict | None = None,
    *,
    job_fn=generate_weekly_report_job,
    timezone: ZoneInfo | None = None,
) -> bool:
    report_config = normalize_report_config(
        config or load_report_config()
    )

    if not report_config.get("enabled", True):
        return False

    if report_config.get("frequency", "weekly") != "weekly":
        return False

    tz = timezone or get_app_timezone()

    scheduler.add_job(
        job_fn,
        CronTrigger(
            day_of_week=report_config["day"],
            hour=report_config["hour"],
            minute=report_config["minute"],
            timezone=tz,
        ),
        id="weekly_report_generation",
        name="Weekly report generation",
        replace_existing=True,
    )
    return True
