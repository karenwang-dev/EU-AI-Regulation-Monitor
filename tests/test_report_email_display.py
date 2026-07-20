import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.web.report_email_helper import resolve_report_email_display


class TestReportEmailDisplayHelper(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        base_path = Path(self.temp_dir.name)
        self.report_config_file = base_path / "report.json"
        self.notification_file = base_path / "notification.json"

        self.notification_file.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "from_address": "monitor@example.com",
                    "to_addresses": ["fallback@example.com"],
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 587,
                    "smtp_username": "monitor@example.com",
                    "smtp_password_env": "SMTP_PASSWORD",
                    "use_tls": True,
                }
            ),
            encoding="utf-8",
        )

        self.env = {
            "OPENAI_API_KEY": "test-openai",
            "FIRECRAWL_API_KEY": "test-firecrawl",
            "SMTP_PASSWORD": "smtp-secret",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_report_config(self, **overrides) -> None:
        config = {
            "enabled": True,
            "frequency": "weekly",
            "day": "mon",
            "hour": 8,
            "minute": 30,
            "email_enabled": True,
            "recipients": ["team@example.com"],
        }
        config.update(overrides)
        self.report_config_file.write_text(
            json.dumps(config),
            encoding="utf-8",
        )

    def _resolve(self, report=None):
        return resolve_report_email_display(
            report,
            report_config_file=self.report_config_file,
            notification_file=self.notification_file,
            environ=self.env,
        )

    def test_disabled_when_email_delivery_off(self):
        self._write_report_config(email_enabled=False)

        result = self._resolve(
            {
                "email_status": "Failed",
                "email_notification": {
                    "status": "Failed",
                    "reason": "Email send failed: SMTP unavailable",
                },
            }
        )

        self.assertEqual(result["display_status"], "Disabled")
        self.assertIsNone(result["status_details"])
        self.assertNotIn("SMTP unavailable", result["status_message"])

    def test_not_configured_when_smtp_password_missing(self):
        self._write_report_config()
        env = {**self.env}
        env.pop("SMTP_PASSWORD")

        result = resolve_report_email_display(
            None,
            report_config_file=self.report_config_file,
            notification_file=self.notification_file,
            environ=env,
        )

        self.assertEqual(result["display_status"], "Not Configured")
        self.assertIn("SMTP_PASSWORD is not set", result["status_details"])

    def test_not_configured_for_invalid_notification_config(self):
        self._write_report_config()
        self.notification_file.write_text("{", encoding="utf-8")

        result = self._resolve()

        self.assertEqual(result["display_status"], "Not Configured")
        self.assertTrue(result["status_details"])

    def test_ready_when_configured_without_report(self):
        self._write_report_config()

        result = self._resolve()

        self.assertEqual(result["display_status"], "Ready")
        self.assertIsNone(result["status_details"])

    def test_sent_status(self):
        self._write_report_config()

        result = self._resolve(
            {
                "email_status": "Sent",
                "email_notification": {
                    "status": "Sent",
                    "sent": True,
                    "reason": "Weekly report email sent.",
                },
            }
        )

        self.assertEqual(result["display_status"], "Sent")
        self.assertIn("sent successfully", result["status_message"])

    def test_failed_status_hides_technical_details_from_message(self):
        self._write_report_config()

        result = self._resolve(
            {
                "email_status": "Failed",
                "email_notification": {
                    "status": "Failed",
                    "reason": "Email send failed: [Errno -2] Name or service not known",
                },
            }
        )

        self.assertEqual(result["display_status"], "Failed")
        self.assertNotIn("Errno", result["status_message"])
        self.assertIn("Name or service not known", result["status_details"])

    def test_configuration_failure_shown_as_not_configured(self):
        self._write_report_config()

        result = self._resolve(
            {
                "email_status": "Failed",
                "email_notification": {
                    "status": "Failed",
                    "reason": "Invalid notification config: Missing required notification field: smtp_host",
                },
            }
        )

        self.assertEqual(result["display_status"], "Not Configured")
        self.assertIn("Missing required notification field", result["status_details"])

    def test_ready_when_previous_delivery_was_disabled(self):
        self._write_report_config()

        result = self._resolve(
            {
                "email_status": "Disabled",
                "email_notification": {
                    "status": "Disabled",
                    "skipped": True,
                    "reason": "Report email delivery is disabled.",
                },
            }
        )

        self.assertEqual(result["display_status"], "Ready")


class TestReportEmailDisplayWeb(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        base_path = Path(self.temp_dir.name)
        self.reports_dir = base_path / "reports"
        self.report_config_file = base_path / "report.json"
        self.notification_file = base_path / "notification.json"

        self.report_config_file.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "frequency": "weekly",
                    "day": "mon",
                    "hour": 8,
                    "minute": 30,
                    "email_enabled": True,
                    "recipients": ["team@example.com"],
                }
            ),
            encoding="utf-8",
        )
        self.notification_file.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "from_address": "monitor@example.com",
                    "to_addresses": ["fallback@example.com"],
                    "smtp_host": "smtp.example.com",
                    "smtp_port": 587,
                    "smtp_username": "monitor@example.com",
                    "smtp_password_env": "SMTP_PASSWORD",
                    "use_tls": True,
                }
            ),
            encoding="utf-8",
        )

        from fastapi.testclient import TestClient
        from app.storage.service import StorageService
        from app.web.app import create_dashboard_app
        from app.report.storage import save_report

        self.store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )
        save_report(
            {
                "title": "Weekly Regulation Monitoring Report",
                "generated_at": "2026-07-16T08:30:00",
                "period": {"start": "2026-07-09", "end": "2026-07-16"},
                "summary": {
                    "total_changes": 1,
                    "high_risk": 1,
                    "medium_risk": 0,
                    "low_risk": 0,
                    "affected_modules": ["Network"],
                },
                "executive_summary": "Summary",
                "key_changes": [],
                "risk_summary": "Risk",
                "email_status": "Sent",
                "email_notification": {
                    "status": "Sent",
                    "sent": True,
                    "reason": "Weekly report email sent.",
                },
            },
            reports_dir=self.reports_dir,
        )
        self.client = TestClient(
            create_dashboard_app(
                storage_service=self.store,
                reports_dir=self.reports_dir,
                report_config_file=self.report_config_file,
                notification_file=self.notification_file,
            )
        )

    def tearDown(self):
        self.client = None
        self.temp_dir.cleanup()

    @patch.dict("os.environ", {"SMTP_PASSWORD": "smtp-secret"}, clear=False)
    def test_report_page_displays_friendly_email_status(self):
        response = self.client.get("/reports")

        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertIn("Email Status", content)
        self.assertIn(">Sent<", content)
        self.assertIn("The latest report email was sent successfully.", content)
        self.assertNotIn("Weekly report email sent.", content.split("Details")[0])

    @patch.dict("os.environ", {"SMTP_PASSWORD": "smtp-secret"}, clear=False)
    def test_report_page_shows_details_for_failed_delivery(self):
        from app.report.storage import save_report

        save_report(
            {
                "title": "Weekly Regulation Monitoring Report",
                "generated_at": "2026-07-16T09:30:00",
                "period": {"start": "2026-07-09", "end": "2026-07-16"},
                "summary": {
                    "total_changes": 0,
                    "high_risk": 0,
                    "medium_risk": 0,
                    "low_risk": 0,
                    "affected_modules": [],
                },
                "executive_summary": "",
                "key_changes": [],
                "risk_summary": "",
                "email_status": "Failed",
                "email_notification": {
                    "status": "Failed",
                    "reason": "Email send failed: SMTP unavailable",
                },
            },
            reports_dir=self.reports_dir,
        )

        response = self.client.get("/reports")

        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertIn(">Failed<", content)
        self.assertIn("The report email could not be delivered.", content)
        self.assertIn("<details", content)
        self.assertIn("SMTP unavailable", content)

    def test_report_page_never_shows_failed_when_email_disabled(self):
        self.report_config_file.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "frequency": "weekly",
                    "day": "mon",
                    "hour": 8,
                    "minute": 30,
                    "email_enabled": False,
                    "recipients": [],
                }
            ),
            encoding="utf-8",
        )

        response = self.client.get("/reports")

        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertIn(">Disabled<", content)
        self.assertNotIn(">Failed<", content)
        self.assertNotIn("SMTP unavailable", content)


if __name__ == "__main__":
    unittest.main()
