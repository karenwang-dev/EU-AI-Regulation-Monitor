import os
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger

from app.scheduler import create_scheduler
from app.utils.datetime_utils import (
    format_utc_iso,
    get_app_timezone,
    parse_legacy_timestamp_as_utc,
    utc_now_iso,
)


class DatetimeUtilsTests(unittest.TestCase):
    def test_utc_now_iso_contains_offset(self):
        value = utc_now_iso()
        self.assertIn("+00:00", value)

    def test_legacy_naive_timestamp_interpreted_as_utc(self):
        parsed = parse_legacy_timestamp_as_utc("2026-07-21T08:00:00")
        self.assertEqual(parsed.tzinfo.utcoffset(None).total_seconds(), 0)
        self.assertEqual(parsed.hour, 8)

    def test_z_suffix_timestamp_parses_as_utc(self):
        parsed = parse_legacy_timestamp_as_utc("2026-07-21T08:00:00Z")
        self.assertEqual(parsed.hour, 8)

    def test_format_utc_iso_normalizes_legacy_naive(self):
        formatted = format_utc_iso("2026-07-21T08:00:00")
        self.assertEqual(formatted, "2026-07-21T08:00:00+00:00")

    def test_utc_to_berlin_summer(self):
        parsed = parse_legacy_timestamp_as_utc("2026-07-21T06:00:00+00:00")
        berlin = parsed.astimezone(ZoneInfo("Europe/Berlin"))
        self.assertEqual(berlin.hour, 8)

    def test_utc_to_berlin_winter(self):
        parsed = parse_legacy_timestamp_as_utc("2026-01-21T07:00:00+00:00")
        berlin = parsed.astimezone(ZoneInfo("Europe/Berlin"))
        self.assertEqual(berlin.hour, 8)

    @patch.dict(os.environ, {"APP_TIMEZONE": "Europe/Berlin"}, clear=False)
    def test_default_app_timezone(self):
        self.assertEqual(str(get_app_timezone()), "Europe/Berlin")

    @patch.dict(os.environ, {"APP_TIMEZONE": "Europe/Berlin"}, clear=False)
    def test_scheduler_daily_trigger_uses_berlin_timezone(self):
        scheduler = create_scheduler()
        daily_trigger = scheduler.get_job("daily_monitors").trigger
        self.assertEqual(
            str(daily_trigger),
            str(CronTrigger(hour=8, minute=0, timezone=ZoneInfo("Europe/Berlin"))),
        )

    @patch.dict(os.environ, {"APP_TIMEZONE": "Europe/Berlin"}, clear=False)
    def test_scheduler_dst_next_fire_is_eight_am_berlin(self):
        tz = ZoneInfo("Europe/Berlin")
        trigger = CronTrigger(hour=8, minute=0, timezone=tz)
        summer_reference = datetime(2026, 7, 21, 0, 0, tzinfo=tz)
        winter_reference = datetime(2026, 1, 21, 0, 0, tzinfo=tz)

        summer_next = trigger.get_next_fire_time(None, summer_reference)
        winter_next = trigger.get_next_fire_time(None, winter_reference)

        self.assertEqual(summer_next.hour, 8)
        self.assertEqual(winter_next.hour, 8)
        self.assertEqual(summer_next.utcoffset().total_seconds(), 7200)
        self.assertEqual(winter_next.utcoffset().total_seconds(), 3600)


class TimestampPersistenceTests(unittest.TestCase):
    def test_new_run_store_timestamp_has_offset(self):
        import sqlite3
        import tempfile
        from pathlib import Path

        from app.monitors.run_store import MonitorRunStore, reset_monitor_run_store

        temp_dir = tempfile.TemporaryDirectory()
        try:
            store = MonitorRunStore(db_path=Path(temp_dir.name) / "storage.db")
            run_id = store.save_run(
                monitor_id="test",
                monitor_name="Test",
                triggered_by="manual_ui",
                execution_status="success",
                change_status="unchanged",
                started_at=utc_now_iso(),
                finished_at=utc_now_iso(),
                duration_ms=100,
                pages_checked=1,
                pages_changed=0,
                homepage_changed=False,
                child_pages_changed=0,
            )
            connection = sqlite3.connect(store.db_path)
            try:
                row = connection.execute(
                    "SELECT started_at, finished_at FROM monitor_runs WHERE id = ?",
                    (run_id,),
                ).fetchone()
            finally:
                connection.close()
            self.assertIn("+00:00", row[0])
            self.assertIn("+00:00", row[1])
        finally:
            reset_monitor_run_store()
            temp_dir.cleanup()


class TimestampApiTests(unittest.TestCase):
    def test_monitor_run_api_returns_offset_timestamps(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock

        from fastapi.testclient import TestClient

        from app.dev.change_test_site import LOCAL_TEST_MONITOR_ID
        from app.monitors.execution import MonitorExecutionService
        from app.monitors.repository import MonitorRepository, reset_monitor_repository
        from app.monitors.run_store import reset_monitor_run_store
        from app.storage.service import StorageService
        from app.web.app import create_dashboard_app

        reset_monitor_repository()
        reset_monitor_run_store()
        temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(temp_dir.name)
        db_path = base_path / "storage.db"
        history_file = base_path / "run_history.json"
        seed_file = base_path / "monitors.json"
        seed_file.write_text(
            json.dumps(
                {
                    "monitors": [
                        {
                            "id": LOCAL_TEST_MONITOR_ID,
                            "name": "Local Multi-page Change Test",
                            "url": "http://127.0.0.1:8080/dev/change-test-site",
                            "keywords": ["policy"],
                            "category": "national_regulation",
                            "frequency": "daily",
                            "enabled": True,
                            "crawl_mode": "single",
                            "max_depth": 0,
                            "max_pages": 1,
                            "skip_ai_analysis": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        repository = MonitorRepository(db_path=db_path, seed_file=seed_file)
        storage = StorageService(
            db_path=db_path,
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )
        execution_service = MonitorExecutionService(
            repository=repository,
            pipeline_factory=lambda: MagicMock(
                process_source=MagicMock(
                    return_value={
                        "source_id": LOCAL_TEST_MONITOR_ID,
                        "status": "unchanged",
                        "page_change_summary": {
                            "pages_checked": 1,
                            "pages_changed": 0,
                            "homepage_changed": False,
                            "child_pages_changed": 0,
                        },
                    }
                )
            ),
            history_file=history_file,
        )
        client = TestClient(
            create_dashboard_app(
                storage_service=storage,
                monitors_repository=repository,
                execution_service=execution_service,
                history_file=history_file,
            )
        )
        try:
            response = client.post(f"/api/monitors/{LOCAL_TEST_MONITOR_ID}/run")
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertIn("+00:00", payload["started_at"])
            self.assertIn("+00:00", payload["finished_at"])
        finally:
            client.close()
            reset_monitor_repository()
            reset_monitor_run_store()
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
