import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.run_history import (
    get_latest_run,
    load_run_history,
    save_run_history,
)
from apscheduler.triggers.cron import CronTrigger

from app.scheduler import create_scheduler, execute_scheduled_run, start_scheduler
from app.utils.datetime_utils import get_app_timezone


class TestRunHistory(unittest.TestCase):

    def test_save_run_history_persists_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            history_file = Path(temp_dir) / "run_history.json"
            results = [
                {"status": "analyzed", "diff_id": 1},
                {"status": "skipped", "diff_id": None},
                {"status": "error", "diff_id": None},
            ]

            entry = save_run_history(results, history_file=history_file)

            self.assertEqual(entry["total_monitors"], 3)
            self.assertIn("+00:00", entry["timestamp"])
            self.assertEqual(entry["changed_count"], 1)
            self.assertEqual(entry["analyzed_count"], 1)
            self.assertEqual(entry["failed_count"], 1)

            saved = load_run_history(history_file=history_file)
            self.assertEqual(len(saved), 1)
            self.assertEqual(get_latest_run(history_file=history_file), saved[0])


class TestScheduler(unittest.TestCase):

    @patch("app.scheduler.save_run_history")
    @patch("app.scheduler.persist_monitor_run")
    @patch("app.scheduler.get_monitor_run_store")
    @patch("app.scheduler.get_monitor_repository")
    @patch("app.scheduler.load_monitors")
    @patch("app.scheduler.run_pipeline")
    def test_execute_scheduled_run_calls_pipeline_and_saves_history(
        self,
        mock_run_pipeline,
        mock_load_monitors,
        mock_get_monitor_repository,
        mock_get_monitor_run_store,
        mock_persist_monitor_run,
        mock_save_run_history,
    ):
        mock_run_pipeline.return_value = [
            {"source_id": "eu_ai_act", "status": "analyzed", "diff_id": 2}
        ]
        mock_load_monitors.return_value = [
            {
                "id": "eu_ai_act",
                "name": "EU AI Act",
                "frequency": "daily",
                "enabled": True,
            }
        ]
        mock_persist_monitor_run.return_value = 42
        mock_save_run_history.return_value = {
            "timestamp": "2026-07-15T12:00:00+00:00",
            "total_monitors": 1,
            "changed_count": 1,
            "analyzed_count": 1,
            "failed_count": 0,
        }

        results = execute_scheduled_run("daily")

        mock_run_pipeline.assert_called_once_with(frequency="daily")
        mock_persist_monitor_run.assert_called_once()
        mock_save_run_history.assert_called_once_with(
            mock_run_pipeline.return_value,
            run_ids=[42],
        )
        self.assertEqual(len(results), 1)

    @patch("app.scheduler.attach_job_run_summary")
    @patch("app.scheduler.save_run_history")
    @patch("app.scheduler.persist_monitor_run")
    @patch("app.scheduler.get_monitor_run_store")
    @patch("app.scheduler.get_monitor_repository")
    @patch("app.scheduler.load_monitors")
    @patch("app.scheduler.run_pipeline")
    def test_execute_scheduled_run_attaches_run_summary(
        self,
        mock_run_pipeline,
        mock_load_monitors,
        mock_get_monitor_repository,
        mock_get_monitor_run_store,
        mock_persist_monitor_run,
        mock_save_run_history,
        mock_attach_summary,
    ):
        mock_run_pipeline.return_value = [
            {"source_id": "eu_ai_act", "status": "skipped", "diff_id": None}
        ]
        mock_load_monitors.return_value = [
            {
                "id": "eu_ai_act",
                "name": "EU AI Act",
                "frequency": "daily",
                "enabled": True,
            }
        ]
        mock_persist_monitor_run.return_value = 7
        mock_save_run_history.return_value = {
            "total_monitors": 1,
            "failed_count": 0,
            "changed_count": 0,
            "analyzed_count": 0,
        }

        execute_scheduled_run("daily")

        mock_attach_summary.assert_called_once_with(
            "daily_monitors",
            mock_save_run_history.return_value,
        )

    def test_scheduler_loads_daily_and_weekly_jobs(self):
        scheduler = create_scheduler()
        job_ids = {job.id for job in scheduler.get_jobs()}

        self.assertEqual(
            job_ids,
            {
                "daily_monitors",
                "weekly_monitors",
                "weekly_report_generation",
            },
        )
        self.assertEqual(len(scheduler.get_jobs()), 3)

    def test_create_scheduler_job_triggers_unchanged(self):
        scheduler = create_scheduler()
        tz = get_app_timezone()

        daily_trigger = scheduler.get_job("daily_monitors").trigger
        weekly_trigger = scheduler.get_job("weekly_monitors").trigger
        report_trigger = scheduler.get_job("weekly_report_generation").trigger

        self.assertEqual(
            str(daily_trigger),
            str(CronTrigger(hour=8, minute=0, timezone=tz)),
        )
        self.assertEqual(
            str(weekly_trigger),
            str(CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=tz)),
        )
        self.assertIn("mon", str(report_trigger).lower())
        self.assertIn("30", str(report_trigger))

    @patch("app.scheduler.release_scheduler_lock")
    @patch("app.scheduler.acquire_scheduler_lock")
    @patch("app.scheduler.logger")
    @patch("app.scheduler.create_scheduler")
    @patch("app.scheduler.load_monitors")
    def test_start_scheduler_logs_triggers_without_next_run_time(
        self,
        mock_load_monitors,
        mock_create_scheduler,
        mock_logger,
        mock_acquire_lock,
        mock_release_lock,
    ):
        mock_acquire_lock.return_value = Path("data/.scheduler.lock")
        mock_load_monitors.return_value = [
            {"frequency": "daily", "enabled": True},
            {"frequency": "weekly", "enabled": True},
        ]

        pending_job = MagicMock(spec=["id", "trigger"])
        pending_job.id = "daily_monitors"
        pending_job.trigger = CronTrigger(hour=8, minute=0, timezone=get_app_timezone())

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = [pending_job]
        mock_create_scheduler.return_value = mock_scheduler

        start_scheduler()

        mock_scheduler.start.assert_called_once()
        mock_acquire_lock.assert_called_once()
        mock_logger.info.assert_any_call("Scheduler lock acquired: %s", Path("data/.scheduler.lock"))

    @patch("app.scheduler.release_scheduler_lock")
    @patch("app.scheduler.acquire_scheduler_lock")
    @patch("app.scheduler.create_scheduler")
    @patch("app.scheduler.load_monitors")
    def test_start_scheduler_does_not_access_next_run_time(
        self,
        mock_load_monitors,
        mock_create_scheduler,
        mock_acquire_lock,
        mock_release_lock,
    ):
        mock_acquire_lock.return_value = Path("data/.scheduler.lock")
        mock_load_monitors.return_value = [{"frequency": "daily", "enabled": True}]

        pending_job = MagicMock()
        pending_job.id = "weekly_monitors"
        pending_job.trigger = CronTrigger(
            day_of_week="mon", hour=8, minute=0, timezone=get_app_timezone()
        )
        del pending_job.next_run_time

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = [pending_job]
        mock_create_scheduler.return_value = mock_scheduler

        start_scheduler()

        mock_scheduler.start.assert_called_once()


class TestCliCommands(unittest.TestCase):

    def _run_main(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "main.py", *args],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
        )

    @patch("app.monitors.repository.log_monitor_repository_state")
    @patch("main.load_monitors")
    @patch("main.run_pipeline")
    @patch("main.save_run_history")
    def test_run_once_command(
        self,
        mock_save_history,
        mock_run_pipeline,
        mock_load_monitors,
        mock_log_monitor_state,
    ):
        mock_load_monitors.return_value = [
            {
                "id": "eu_ai_act",
                "name": "EU AI Act",
                "enabled": True,
                "frequency": "daily",
                "crawl_mode": "single",
                "skip_ai_analysis": False,
            }
        ]
        mock_run_pipeline.return_value = [
            {
                "name": "EU AI Act",
                "status": "skipped",
                "snapshot_id": 1,
                "diff_id": None,
                "analysis_id": None,
            }
        ]
        mock_save_history.return_value = {
            "timestamp": "2026-07-15T12:00:00",
            "total_monitors": 1,
            "changed_count": 0,
            "analyzed_count": 0,
            "failed_count": 0,
        }

        import main

        exit_code = main.run_once()

        self.assertEqual(exit_code, 0)
        mock_run_pipeline.assert_called_once_with()
        mock_save_history.assert_called_once()

    @patch("main.get_latest_run")
    @patch("main.load_monitors")
    def test_status_command(self, mock_load_monitors, mock_get_latest_run):
        mock_load_monitors.return_value = [
            {
                "id": "eu_ai_act",
                "enabled": True,
                "frequency": "daily",
            },
            {
                "id": "boe",
                "enabled": True,
                "frequency": "weekly",
            },
        ]
        mock_get_latest_run.return_value = {
            "timestamp": "2026-07-15T12:00:00",
            "total_monitors": 2,
            "changed_count": 1,
            "analyzed_count": 1,
            "failed_count": 0,
        }

        import main

        exit_code = main.show_status()

        self.assertEqual(exit_code, 0)

    def test_cli_usage_for_unknown_command(self):
        result = self._run_main("unknown-command")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)


if __name__ == "__main__":
    unittest.main()
