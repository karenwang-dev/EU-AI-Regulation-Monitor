import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.notification.email_sender import EmailSendError
from app.report.email_sender import build_report_email_html, send_report_email
from app.report.generation import create_and_save_weekly_report
from app.report.notifier import notify_weekly_report


class TestReportEmail(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        base_path = Path(self.temp_dir.name)
        self.reports_dir = base_path / "reports"
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
                    "subject_prefix": "[AI Regulation Monitor]",
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _sample_report(self) -> dict:
        return {
            "id": "2026-07-16_weekly_report",
            "filename": "2026-07-16_weekly_report.json",
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
            "executive_summary": "One high-risk change requires review.",
            "key_changes": [
                {
                    "title": "EU AI Act Update",
                    "impact_level": "HIGH",
                    "affected_modules": ["Network"],
                    "recommended_actions": ["Review controls"],
                }
            ],
            "risk_summary": "HIGH risk changes affect network modules.",
        }

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

    def test_build_report_email_html_contains_report_sections(self):
        html_body = build_report_email_html(self._sample_report())

        self.assertIn("Executive Summary", html_body)
        self.assertIn("EU AI Act Update", html_body)
        self.assertIn("Risk Summary", html_body)

    @patch("app.report.email_sender.smtplib.SMTP")
    def test_send_report_email_sends_html_with_attachment(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        attachment_path = self.reports_dir / "2026-07-16_weekly_report.json"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        attachment_path.write_text("{}", encoding="utf-8")

        send_report_email(
            self._sample_report(),
            {
                "from_address": "monitor@example.com",
                "to_addresses": ["team@example.com"],
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "use_tls": True,
            },
            attachment_path=attachment_path,
        )

        mock_server.starttls.assert_called_once()
        mock_server.sendmail.assert_called_once()
        sent_message = mock_server.sendmail.call_args.args[2]
        self.assertIn("text/html", sent_message)
        self.assertIn("2026-07-16_weekly_report.json", sent_message)

    def test_notify_weekly_report_disabled_skips(self):
        self._write_report_config(email_enabled=False)

        result = notify_weekly_report(
            self._sample_report(),
            report_config_file=self.report_config_file,
            notification_file=self.notification_file,
            send_report_email_fn=MagicMock(),
        )

        self.assertEqual(result["status"], "Disabled")
        self.assertTrue(result["skipped"])

    def test_notify_weekly_report_missing_recipients_skips(self):
        self._write_report_config(recipients=[])

        send_mock = MagicMock()
        result = notify_weekly_report(
            self._sample_report(),
            report_config_file=self.report_config_file,
            notification_file=self.notification_file,
            send_report_email_fn=send_mock,
        )

        self.assertEqual(result["status"], "Disabled")
        send_mock.assert_not_called()

    def test_notify_weekly_report_enabled_sends(self):
        self._write_report_config()
        send_mock = MagicMock()

        result = notify_weekly_report(
            self._sample_report(),
            report_config_file=self.report_config_file,
            notification_file=self.notification_file,
            send_report_email_fn=send_mock,
        )

        self.assertEqual(result["status"], "Sent")
        self.assertTrue(result["sent"])
        send_mock.assert_called_once()

    def test_notify_weekly_report_smtp_failure_handled(self):
        self._write_report_config()
        send_mock = MagicMock(side_effect=EmailSendError("SMTP unavailable"))

        result = notify_weekly_report(
            self._sample_report(),
            report_config_file=self.report_config_file,
            notification_file=self.notification_file,
            send_report_email_fn=send_mock,
        )

        self.assertEqual(result["status"], "Failed")
        self.assertFalse(result["sent"])

    def test_generation_continues_after_email_failure(self):
        report_data = {
            "period": {"start": "2026-07-09", "end": "2026-07-16"},
            "summary": {
                "total_changes": 0,
                "high_risk": 0,
                "medium_risk": 0,
                "low_risk": 0,
                "affected_modules": [],
            },
            "changes": [],
        }
        generated = {
            "title": "Weekly Regulation Monitoring Report",
            "executive_summary": "",
            "key_changes": [],
            "risk_summary": "",
            "generated_at": "2026-07-16T08:30:00",
        }

        result = create_and_save_weekly_report(
            reports_dir=self.reports_dir,
            build_weekly_report_fn=lambda **kwargs: report_data,
            generate_weekly_report_fn=lambda data, client=None: generated,
            notify_weekly_report_fn=MagicMock(
                side_effect=RuntimeError("notification crashed")
            ),
        )

        self.assertEqual(result["title"], "Weekly Regulation Monitoring Report")
        self.assertEqual(result["email_status"], "Failed")
        self.assertIn("id", result)


class TestReportEmailWeb(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        base_path = Path(self.temp_dir.name)
        self.reports_dir = base_path / "reports"

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
                    "reason": "Weekly report email sent.",
                },
            },
            reports_dir=self.reports_dir,
        )
        self.client = TestClient(
            create_dashboard_app(
                storage_service=self.store,
                reports_dir=self.reports_dir,
            )
        )

    def tearDown(self):
        self.client = None
        self.temp_dir.cleanup()

    def test_report_page_displays_email_status(self):
        response = self.client.get("/reports")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Email Status", content)
        self.assertIn(b">Sent<", content)


if __name__ == "__main__":
    unittest.main()
