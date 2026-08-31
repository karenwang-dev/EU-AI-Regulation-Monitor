import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.scheduler_status import (
    HEARTBEAT_STALE_SECONDS,
    attach_job_run_summary,
    build_scheduler_dashboard_view,
    get_scheduler_health_status,
    get_scheduler_process_status,
    record_job_failure,
    record_job_start,
    record_job_success,
    record_scheduler_heartbeat,
    record_scheduler_process_start,
)


class TestSchedulerObservability(unittest.TestCase):

    def test_process_status_unknown_without_heartbeat(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"
            status_file.write_text(
                json.dumps(
                    {
                        "jobs": {
                            "daily_monitors": {
                                "status": "success",
                                "started_at": "2026-08-31T08:00:00+00:00",
                                "completed_at": "2026-08-31T08:00:30+00:00",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                get_scheduler_process_status(status_file=status_file),
                "UNKNOWN",
            )
            self.assertEqual(
                get_scheduler_health_status(status_file=status_file),
                "ok",
            )

    def test_process_status_running_with_fresh_heartbeat(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"
            now = datetime.now(timezone.utc).isoformat()
            status_file.write_text(
                json.dumps(
                    {
                        "process": {
                            "pid": 1234,
                            "heartbeat_at": now,
                            "started_at": now,
                            "timezone": "Europe/Berlin",
                        },
                        "jobs": {},
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                get_scheduler_process_status(status_file=status_file),
                "RUNNING",
            )
            self.assertEqual(
                get_scheduler_health_status(status_file=status_file),
                "running",
            )

    def test_process_status_not_running_with_stale_heartbeat(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"
            stale = (
                datetime.now(timezone.utc)
                - timedelta(seconds=HEARTBEAT_STALE_SECONDS + 30)
            ).isoformat()
            status_file.write_text(
                json.dumps(
                    {
                        "process": {
                            "pid": 1234,
                            "heartbeat_at": stale,
                            "started_at": stale,
                        },
                        "jobs": {
                            "daily_monitors": {
                                "status": "success",
                                "completed_at": stale,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                get_scheduler_process_status(status_file=status_file),
                "NOT RUNNING",
            )

    def test_record_job_success_includes_run_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"

            record_job_start("daily_monitors", status_file=status_file)
            attach_job_run_summary(
                "daily_monitors",
                {
                    "total_monitors": 16,
                    "failed_count": 1,
                    "changed_count": 2,
                    "analyzed_count": 2,
                },
            )
            record_job_success("daily_monitors", status_file=status_file)

            data = json.loads(status_file.read_text(encoding="utf-8"))
            summary = data["jobs"]["daily_monitors"]["run_summary"]
            self.assertEqual(summary["total_monitors"], 16)
            self.assertEqual(summary["failed_count"], 1)

    def test_build_scheduler_dashboard_view(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"
            now = datetime.now(timezone.utc).isoformat()
            next_run = (
                datetime.now(timezone.utc) + timedelta(days=1)
            ).isoformat()
            status_file.write_text(
                json.dumps(
                    {
                        "process": {
                            "heartbeat_at": now,
                            "timezone": "Europe/Berlin",
                        },
                        "next_runs": {
                            "daily_monitors": next_run,
                            "weekly_monitors": next_run,
                        },
                        "jobs": {
                            "daily_monitors": {
                                "status": "success",
                                "completed_at": now,
                                "run_summary": {
                                    "total_monitors": 16,
                                    "failed_count": 0,
                                    "changed_count": 1,
                                    "analyzed_count": 1,
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            view = build_scheduler_dashboard_view(
                enabled_monitor_count=16,
                status_file=status_file,
            )

            self.assertEqual(view["process_status"], "RUNNING")
            self.assertEqual(view["last_run_result"], "SUCCESS")
            self.assertEqual(view["enabled_monitor_count"], 16)
            self.assertEqual(view["last_run_total_monitors"], 16)
            self.assertEqual(view["next_run_at"], next_run)

    def test_record_scheduler_process_start_reads_next_run_after_start(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"
            scheduler = MagicMock()
            job = MagicMock()
            job.id = "daily_monitors"
            job.next_run_time = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)
            scheduler.get_jobs.return_value = [job]

            record_scheduler_process_start(scheduler, status_file=status_file)

            data = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertIn("daily_monitors", data["next_runs"])
            self.assertIsNotNone(data["next_runs"]["daily_monitors"])

    def test_record_scheduler_heartbeat_updates_next_runs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"
            scheduler = MagicMock()
            job = MagicMock()
            job.id = "weekly_monitors"
            job.next_run_time = datetime(2026, 9, 8, 8, 0, tzinfo=timezone.utc)
            scheduler.get_jobs.return_value = [job]

            record_scheduler_heartbeat(scheduler, status_file=status_file)

            data = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(
                get_scheduler_process_status(status_file=status_file),
                "RUNNING",
            )
            self.assertIn("weekly_monitors", data["next_runs"])

    def test_partial_last_run_result(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            status_file = Path(temp_dir) / "scheduler_status.json"
            now = datetime.now(timezone.utc).isoformat()
            status_file.write_text(
                json.dumps(
                    {
                        "process": {"heartbeat_at": now},
                        "jobs": {
                            "weekly_monitors": {
                                "status": "success",
                                "completed_at": now,
                                "run_summary": {
                                    "total_monitors": 10,
                                    "failed_count": 2,
                                    "changed_count": 1,
                                    "analyzed_count": 1,
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            view = build_scheduler_dashboard_view(
                enabled_monitor_count=16,
                status_file=status_file,
            )
            self.assertEqual(view["last_run_result"], "PARTIAL")


if __name__ == "__main__":
    unittest.main()
