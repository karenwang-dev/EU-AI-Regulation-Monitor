from __future__ import annotations

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger

from app.report.config import load_report_config, normalize_report_config


def generate_weekly_report_job(
    *,
    create_and_save_weekly_report_fn=None,
) -> dict:
    if create_and_save_weekly_report_fn is None:
        from app.report.generation import create_and_save_weekly_report

        create_and_save_weekly_report_fn = create_and_save_weekly_report

    print("=" * 60)
    print("Weekly report generation started")
    print("=" * 60)

    stored_report = create_and_save_weekly_report_fn()

    print("\n" + "=" * 60)
    print("Weekly report generation completed")
    print(f"Report ID: {stored_report.get('id', 'unknown')}")
    print(
        "Total changes: "
        f"{stored_report.get('summary', {}).get('total_changes', 0)}"
    )
    print("=" * 60)

    return stored_report


def schedule_weekly_report(
    scheduler: BaseScheduler,
    config: dict | None = None,
    *,
    job_fn=generate_weekly_report_job,
) -> bool:
    report_config = normalize_report_config(
        config or load_report_config()
    )

    if not report_config.get("enabled", True):
        return False

    if report_config.get("frequency", "weekly") != "weekly":
        return False

    scheduler.add_job(
        job_fn,
        CronTrigger(
            day_of_week=report_config["day"],
            hour=report_config["hour"],
            minute=report_config["minute"],
        ),
        id="weekly_report_generation",
        name="Weekly report generation",
        replace_existing=True,
    )
    return True
