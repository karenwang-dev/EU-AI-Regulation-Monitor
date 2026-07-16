from __future__ import annotations

import json
from pathlib import Path

from apscheduler.schedulers.base import BaseScheduler
from apscheduler.triggers.cron import CronTrigger

from app.report.generation import create_and_save_weekly_report

REPORT_CONFIG_FILE = Path("config/report.json")

DEFAULT_REPORT_CONFIG = {
    "enabled": True,
    "frequency": "weekly",
    "day": "mon",
    "hour": 8,
    "minute": 30,
}

DAY_ALIASES = {
    "mon": "mon",
    "monday": "mon",
    "tue": "tue",
    "tuesday": "tue",
    "wed": "wed",
    "wednesday": "wed",
    "thu": "thu",
    "thursday": "thu",
    "fri": "fri",
    "friday": "fri",
    "sat": "sat",
    "saturday": "sat",
    "sun": "sun",
    "sunday": "sun",
}


def load_report_config(
    config_file: Path | str | None = None,
) -> dict:
    path = Path(config_file) if config_file is not None else REPORT_CONFIG_FILE
    if not path.exists():
        return DEFAULT_REPORT_CONFIG.copy()

    with open(path, "r", encoding="utf-8") as file:
        raw_config = json.load(file)

    if not isinstance(raw_config, dict):
        return DEFAULT_REPORT_CONFIG.copy()

    config = DEFAULT_REPORT_CONFIG.copy()
    config.update(raw_config)
    return _normalize_report_config(config)


def _normalize_report_config(config: dict) -> dict:
    day = str(config.get("day", "mon")).strip().lower()
    config["day"] = DAY_ALIASES.get(day, "mon")

    try:
        config["hour"] = int(config.get("hour", 8))
    except (TypeError, ValueError):
        config["hour"] = 8

    try:
        config["minute"] = int(config.get("minute", 30))
    except (TypeError, ValueError):
        config["minute"] = 30

    config["hour"] = max(0, min(config["hour"], 23))
    config["minute"] = max(0, min(config["minute"], 59))
    config["enabled"] = bool(config.get("enabled", True))
    config["frequency"] = str(config.get("frequency", "weekly")).strip().lower()
    return config


def generate_weekly_report_job(
    *,
    create_and_save_weekly_report_fn=create_and_save_weekly_report,
) -> dict:
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
    report_config = _normalize_report_config(
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
