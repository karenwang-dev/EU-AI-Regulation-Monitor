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
from app.scheduler import create_scheduler, execute_scheduled_run


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
            self.assertEqual(entry["changed_count"], 1)
            self.assertEqual(entry["analyzed_count"], 1)
            self.assertEqual(entry["failed_count"], 1)

            saved = load_run_history(history_file=history_file)
            self.assertEqual(len(saved), 1)
            self.assertEqual(get_latest_run(history_file=history_file), saved[0])


class TestScheduler(unittest.TestCase):

    @patch("app.scheduler.save_run_history")
    @patch("app.scheduler.run_pipeline")
    def test_execute_scheduled_run_calls_pipeline_and_saves_history(
        self,
        mock_run_pipeline,
        mock_save_run_history,
    ):
        mock_run_pipeline.return_value = [
            {"status": "analyzed", "diff_id": 2}
        ]
        mock_save_run_history.return_value = {
            "timestamp": "2026-07-15T12:00:00",
            "total_monitors": 1,
            "changed_count": 1,
            "analyzed_count": 1,
            "failed_count": 0,
        }

        results = execute_scheduled_run("daily")

        mock_run_pipeline.assert_called_once_with(frequency="daily")
        mock_save_run_history.assert_called_once_with(
            mock_run_pipeline.return_value
        )
        self.assertEqual(len(results), 1)

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


class TestCliCommands(unittest.TestCase):

    def _run_main(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "main.py", *args],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
        )

    @patch("main.run_pipeline")
    @patch("main.save_run_history")
    def test_run_once_command(self, mock_save_history, mock_run_pipeline):
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
