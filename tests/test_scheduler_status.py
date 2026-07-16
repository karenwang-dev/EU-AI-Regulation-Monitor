import json
import tempfile
import unittest
from pathlib import Path

from app.scheduler_status import (
    get_scheduler_health_status,
    record_job_failure,
    record_job_start,
    record_job_success,
)


class TestSchedulerStatus(unittest.TestCase):

    def test_record_job_start_persists_running_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"

            record_job_start("daily_monitors", status_file=status_file)

            data = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(data["jobs"]["daily_monitors"]["status"], "running")
            self.assertIsNotNone(data["jobs"]["daily_monitors"]["started_at"])

    def test_record_job_success_updates_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"

            record_job_start("weekly_monitors", status_file=status_file)
            record_job_success("weekly_monitors", status_file=status_file)

            data = json.loads(status_file.read_text(encoding="utf-8"))
            job = data["jobs"]["weekly_monitors"]
            self.assertEqual(job["status"], "success")
            self.assertIsNotNone(job["completed_at"])
            self.assertIsNone(job["last_error"])

    def test_record_job_failure_stores_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"

            record_job_start(
                "weekly_report_generation",
                status_file=status_file,
            )
            record_job_failure(
                "weekly_report_generation",
                "SMTP timeout",
                status_file=status_file,
            )

            data = json.loads(status_file.read_text(encoding="utf-8"))
            job = data["jobs"]["weekly_report_generation"]
            self.assertEqual(job["status"], "failure")
            self.assertEqual(job["last_error"], "SMTP timeout")

    def test_get_scheduler_health_status_unknown_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"

            self.assertEqual(
                get_scheduler_health_status(status_file=status_file),
                "unknown",
            )

    def test_get_scheduler_health_status_ok_after_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"

            record_job_start("daily_monitors", status_file=status_file)
            record_job_success("daily_monitors", status_file=status_file)

            self.assertEqual(
                get_scheduler_health_status(status_file=status_file),
                "ok",
            )

    def test_get_scheduler_health_status_running(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"

            record_job_start("daily_monitors", status_file=status_file)

            self.assertEqual(
                get_scheduler_health_status(status_file=status_file),
                "running",
            )

    def test_get_scheduler_health_status_error_after_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"

            record_job_failure(
                "weekly_monitors",
                "Pipeline error",
                status_file=status_file,
            )

            self.assertEqual(
                get_scheduler_health_status(status_file=status_file),
                "error",
            )


if __name__ == "__main__":
    unittest.main()
