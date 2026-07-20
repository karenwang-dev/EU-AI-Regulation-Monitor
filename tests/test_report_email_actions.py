import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.notification.email_sender import EmailSendError, humanize_smtp_error
from app.report.storage import save_report
from app.storage.service import StorageService
from app.web.app import create_dashboard_app
from app.web.report_email_helper import (
    contains_sensitive_secret,
    deliver_report_email,
    resolve_report_email_display,
    send_test_report_email,
)


class TestReportEmailHelperActions(unittest.TestCase):

    def test_humanize_smtp_error_messages(self):
        self.assertIn(
            "Unable to resolve the SMTP server hostname",
            humanize_smtp_error("[Errno -2] Name or service not known"),
        )
        self.assertIn(
            "SMTP authentication failed",
            humanize_smtp_error("535 Authentication failed"),
        )
        self.assertIn(
            "refused the connection",
            humanize_smtp_error("Connection refused"),
        )
        self.assertIn(
            "does not support the selected security mode",
            humanize_smtp_error("STARTTLS extension not supported by server"),
        )

    def test_contains_sensitive_secret_detects_password_leaks(self):
        self.assertTrue(contains_sensitive_secret("SMTP_PASSWORD=secret-value"))
        with patch.dict("os.environ", {"SMTP_PASSWORD": "secret-value"}, clear=False):
            self.assertTrue(contains_sensitive_secret("failed with secret-value"))


class TestReportEmailActions(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        base_path = Path(self.temp_dir.name)
        self.reports_dir = base_path / "reports"
        self.report_config_file = base_path / "report.json"
        self.notification_file = base_path / "notification.json"
        self.settings_file = base_path / "email_settings.json"
        self.missing_email_settings = base_path / "missing_email_settings.json"

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

        self.store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )
        self.saved_report = save_report(
            self._sample_report(),
            reports_dir=self.reports_dir,
        )
        self.client = self._create_client()

    def _create_client(
        self,
        deliver_report_email_fn=None,
        send_test_report_email_fn=None,
    ):
        return TestClient(
            create_dashboard_app(
                storage_service=self.store,
                reports_dir=self.reports_dir,
                report_config_file=self.report_config_file,
                notification_file=self.notification_file,
                email_settings_file=self.settings_file,
                deliver_report_email_fn=deliver_report_email_fn,
                send_test_report_email_fn=send_test_report_email_fn,
            )
        )

    def tearDown(self):
        self.client = None
        self.temp_dir.cleanup()

    def _sample_report(self, **overrides) -> dict:
        report = {
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
            "email_status": "Ready",
        }
        report.update(overrides)
        return report

    @patch.dict("os.environ", {"SMTP_PASSWORD": "smtp-secret"}, clear=False)
    def test_ready_state_shows_send_and_test_actions(self):
        ready_report = save_report(
            self._sample_report(
                generated_at="2026-07-16T09:00:00",
                email_status="Disabled",
                email_notification={
                    "status": "Disabled",
                    "skipped": True,
                    "reason": "Report email delivery is disabled.",
                },
            ),
            reports_dir=self.reports_dir,
        )

        display = resolve_report_email_display(
            ready_report,
            report_config_file=self.report_config_file,
            notification_file=self.notification_file,
            email_settings_file=self.missing_email_settings,
        )
        self.assertEqual(display["display_status"], "Ready")

        response = self.client.get("/reports")
        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertIn("Send Email", content)
        self.assertIn("Send Test Email", content)
        self.assertIn("smtp.example.com", content)
        self.assertIn("team@example.com", content)
        self.assertNotIn("smtp-secret", content)
        self.assertNotIn("SMTP_PASSWORD", content)

    def test_disabled_state_blocks_send_actions(self):
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
        self.assertIn(">Disabled<", response.text)
        self.assertNotIn("Send Email", response.text)

        send_response = self.client.post(
            f"/api/reports/{self.saved_report['id']}/email/send"
        )
        self.assertEqual(send_response.status_code, 400)

    def test_missing_configuration_state(self):
        self.report_config_file.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "frequency": "weekly",
                    "day": "mon",
                    "hour": 8,
                    "minute": 30,
                    "email_enabled": True,
                    "recipients": [],
                }
            ),
            encoding="utf-8",
        )

        display = resolve_report_email_display(
            self.saved_report,
            report_config_file=self.report_config_file,
            notification_file=self.notification_file,
            email_settings_file=self.missing_email_settings,
        )
        self.assertEqual(display["display_status"], "Disabled")

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
        with patch.dict("os.environ", {}, clear=True):
            display_missing_smtp = resolve_report_email_display(
                self.saved_report,
                report_config_file=self.report_config_file,
                notification_file=self.notification_file,
                email_settings_file=self.missing_email_settings,
                environ={},
            )
        self.assertEqual(display_missing_smtp["display_status"], "Not Configured")

    @patch.dict("os.environ", {"SMTP_PASSWORD": "smtp-secret"}, clear=False)
    def test_successful_manual_send(self):
        notify_mock = MagicMock(
            return_value={
                "sent": True,
                "skipped": False,
                "status": "Sent",
                "reason": "Weekly report email sent.",
            }
        )

        def deliver_fn(report, **kwargs):
            return deliver_report_email(
                report,
                reports_dir=self.reports_dir,
                report_config_file=self.report_config_file,
                notification_file=self.notification_file,
                notify_weekly_report_fn=notify_mock,
            )

        client = self._create_client(deliver_report_email_fn=deliver_fn)

        ready_report = save_report(
            self._sample_report(
                generated_at="2026-07-16T09:00:00",
                email_status="Ready",
            ),
            reports_dir=self.reports_dir,
        )

        response = client.post(
            f"/api/reports/{ready_report['id']}/email/send"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email_status"], "Sent")
        notify_mock.assert_called_once()

    @patch.dict("os.environ", {"SMTP_PASSWORD": "smtp-secret"}, clear=False)
    def test_failed_manual_send_returns_humanized_error(self):
        notify_mock = MagicMock(
            return_value={
                "sent": False,
                "skipped": False,
                "status": "Failed",
                "reason": "Email send failed: [Errno -2] Name or service not known",
            }
        )

        updated = deliver_report_email(
            self.saved_report,
            reports_dir=self.reports_dir,
            report_config_file=self.report_config_file,
            notification_file=self.notification_file,
            notify_weekly_report_fn=notify_mock,
        )

        self.assertEqual(updated["email_status"], "Failed")
        self.assertIn(
            "Unable to resolve the SMTP server hostname",
            updated["email_notification"]["reason"],
        )
        self.assertIn(
            "Name or service not known",
            updated["email_notification"]["technical_details"],
        )

    @patch.dict("os.environ", {"SMTP_PASSWORD": "smtp-secret"}, clear=False)
    def test_retry_action_uses_same_delivery_path(self):
        notify_mock = MagicMock(
            return_value={
                "sent": True,
                "skipped": False,
                "status": "Sent",
                "reason": "Weekly report email sent.",
            }
        )

        def deliver_fn(report, **kwargs):
            return deliver_report_email(
                report,
                reports_dir=self.reports_dir,
                report_config_file=self.report_config_file,
                notification_file=self.notification_file,
                notify_weekly_report_fn=notify_mock,
            )

        client = self._create_client(deliver_report_email_fn=deliver_fn)

        failed_report = save_report(
            self._sample_report(
                generated_at="2026-07-16T10:00:00",
                email_status="Failed",
                email_notification={
                    "status": "Failed",
                    "reason": "Unable to connect to the SMTP server. Check the SMTP host, port, network, firewall, VPN, and SSL/TLS mode.",
                    "technical_details": "Email send failed: Connection refused",
                },
            ),
            reports_dir=self.reports_dir,
        )

        page = client.get("/reports")
        self.assertIn("Retry Email", page.text)

        response = client.post(
            f"/api/reports/{failed_report['id']}/email/retry"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email_status"], "Sent")
        notify_mock.assert_called_once()

    @patch.dict("os.environ", {"SMTP_PASSWORD": "smtp-secret"}, clear=False)
    def test_test_email_action_does_not_generate_report(self):
        send_mock = MagicMock()

        def send_test_fn(**kwargs):
            return send_test_report_email(
                report_config_file=self.report_config_file,
                notification_file=self.notification_file,
                send_email_fn=send_mock,
            )

        client = self._create_client(send_test_report_email_fn=send_test_fn)
        response = client.post("/api/reports/email/test")

        self.assertEqual(response.status_code, 200)
        send_mock.assert_called_once()
        subject = send_mock.call_args.args[1]
        body = send_mock.call_args.args[2]
        self.assertEqual(subject, "AI Regulation Monitor")
        self.assertEqual(body, "This is a successful SMTP configuration test.")

    @patch.dict("os.environ", {"SMTP_PASSWORD": "legacy-gmail-password"}, clear=False)
    @patch(
        "app.config.email_settings.decrypt_secret",
        return_value="hisense-password",
    )
    def test_report_test_email_prefers_saved_ui_settings_over_legacy_env(
        self,
        decrypt_mock,
    ):
        from app.config.email_settings import save_email_settings

        key_file = self.temp_dir.name + "/email_settings.key"
        save_email_settings(
            {
                "provider": "hisense",
                "username": "user@hisense.com",
                "password": "hisense-password",
                "recipients": ["recipient@example.com"],
            },
            settings_file=self.settings_file,
            key_file=Path(key_file),
        )
        send_mock = MagicMock()

        def send_test_fn(**kwargs):
            return send_test_report_email(
                report_config_file=self.report_config_file,
                notification_file=self.notification_file,
                email_settings_file=self.settings_file,
                send_email_fn=send_mock,
            )

        client = self._create_client(send_test_report_email_fn=send_test_fn)
        response = client.post("/api/reports/email/test")

        self.assertEqual(response.status_code, 200)
        send_mock.assert_called_once()
        smtp_config = send_mock.call_args.args[0]
        self.assertEqual(smtp_config["provider"], "hisense")
        self.assertEqual(smtp_config["smtp_host"], "mail.hisense.com")
        self.assertEqual(smtp_config["smtp_port"], 465)
        self.assertTrue(smtp_config["use_ssl"])
        self.assertFalse(smtp_config["use_tls"])

    @patch.dict("os.environ", {"SMTP_PASSWORD": "smtp-secret"}, clear=False)
    def test_test_email_failure_is_humanized(self):
        result = send_test_report_email(
            report_config_file=self.report_config_file,
            notification_file=self.notification_file,
            send_email_fn=MagicMock(
                side_effect=EmailSendError("535 Authentication failed")
            ),
        )

        self.assertFalse(result["ok"])
        self.assertIn("SMTP authentication failed", result["message"])


if __name__ == "__main__":
    unittest.main()
