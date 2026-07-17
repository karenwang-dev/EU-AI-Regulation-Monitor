import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from apscheduler.schedulers.background import BackgroundScheduler

from app.report.config import load_report_config
from app.report.scheduler import (
    generate_weekly_report_job,
    schedule_weekly_report,
)
from app.scheduler import create_scheduler


class TestReportScheduler(unittest.TestCase):

    def test_load_report_config_uses_defaults_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_report_config(
                config_file=Path(temp_dir) / "missing-report.json"
            )

        self.assertTrue(config["enabled"])
        self.assertEqual(config["frequency"], "weekly")
        self.assertEqual(config["day"], "mon")
        self.assertEqual(config["hour"], 8)
        self.assertEqual(config["minute"], 30)
        self.assertFalse(config["email_enabled"])
        self.assertEqual(config["recipients"], [])

    def test_load_report_config_merges_file_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "report.json"
            config_path.write_text(
                json.dumps(
                    {
                        "enabled": False,
                        "day": "friday",
                        "hour": 9,
                        "minute": 15,
                    }
                ),
                encoding="utf-8",
            )

            config = load_report_config(config_file=config_path)

        self.assertFalse(config["enabled"])
        self.assertEqual(config["day"], "fri")
        self.assertEqual(config["hour"], 9)
        self.assertEqual(config["minute"], 15)

    def test_scheduler_loads_report_job(self):
        scheduler = create_scheduler()
        job_ids = {job.id for job in scheduler.get_jobs()}

        self.assertIn("weekly_report_generation", job_ids)
        self.assertIn("daily_monitors", job_ids)
        self.assertIn("weekly_monitors", job_ids)

        report_job = scheduler.get_job("weekly_report_generation")
        self.assertIsNotNone(report_job)
        self.assertEqual(report_job.name, "Weekly report generation")

    def test_disabled_config_skips_report_job(self):
        scheduler = BackgroundScheduler()
        scheduled = schedule_weekly_report(
            scheduler,
            config={
                "enabled": False,
                "frequency": "weekly",
                "day": "mon",
                "hour": 8,
                "minute": 30,
            },
        )

        self.assertFalse(scheduled)
        self.assertIsNone(scheduler.get_job("weekly_report_generation"))

    def test_generate_weekly_report_job_calls_generation_pipeline(self):
        mock_create_and_save = MagicMock(
            return_value={
                "id": "2026-07-16_weekly_report",
                "summary": {"total_changes": 2, "high_risk": 1},
            }
        )

        result = generate_weekly_report_job(
            create_and_save_weekly_report_fn=mock_create_and_save,
        )

        mock_create_and_save.assert_called_once_with()
        self.assertEqual(result["id"], "2026-07-16_weekly_report")

    @patch("main.create_and_save_weekly_report")
    def test_cli_generate_report_command(self, mock_create_and_save):
        mock_create_and_save.return_value = {
            "id": "2026-07-16_weekly_report",
            "generated_at": "2026-07-16T08:30:00",
            "summary": {
                "total_changes": 1,
                "high_risk": 1,
            },
        }

        import main

        exit_code = main.generate_report()

        self.assertEqual(exit_code, 0)
        mock_create_and_save.assert_called_once_with()

    @patch("main.create_and_save_weekly_report")
    def test_cli_generate_report_entrypoint(self, mock_create_and_save):
        mock_create_and_save.return_value = {
            "id": "2026-07-16_weekly_report",
            "generated_at": "2026-07-16T08:30:00",
            "summary": {"total_changes": 0, "high_risk": 0},
        }

        import main

        with patch.object(sys, "argv", ["main.py", "generate-report"]):
            with self.assertLogs("regulation_monitor.main", level="INFO") as logs:
                exit_code = main.main()

        self.assertEqual(exit_code, 0)
        output = "\n".join(logs.output)
        self.assertIn("Weekly Regulation Report Generation", output)
        self.assertIn("2026-07-16_weekly_report", output)
        mock_create_and_save.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
