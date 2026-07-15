import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.notification.email_sender import EmailSendError
from app.notification.notifier import (
    build_email_content,
    load_notification_config,
    notify_if_needed,
    should_notify,
)


class TestNotification(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.notification_file = Path(self.temp_dir.name) / "notification.json"
        self.notification_file.write_text(
            json.dumps(
                {
                    "enabled": True,
                    "from_address": "monitor@example.com",
                    "to_addresses": ["team@example.com"],
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

        self.monitor = {
            "id": "eu_ai_act",
            "name": "EU AI Act",
            "url": "https://example.com/ai-act",
            "keywords": ["AI Act"],
            "category": "AI Regulation",
            "frequency": "daily",
            "enabled": True,
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_high_triggers_email(self):
        send_mock = MagicMock()
        analysis = {
            "impact_level": "HIGH",
            "affected_modules": ["Network"],
            "reason": "Critical update.",
            "recommended_actions": ["Review controls"],
            "confidence": "HIGH",
        }

        result = notify_if_needed(
            self.monitor,
            analysis,
            snapshot_id=42,
            notification_file=self.notification_file,
            send_email_fn=send_mock,
        )

        self.assertTrue(result["sent"])
        send_mock.assert_called_once()
        subject, body = send_mock.call_args.args[1], send_mock.call_args.args[2]
        self.assertIn("HIGH impact detected", subject)
        self.assertIn("Snapshot ID: 42", body)

    def test_low_does_not_trigger_email(self):
        send_mock = MagicMock()
        analysis = {
            "impact_level": "LOW",
            "affected_modules": [],
            "reason": "Minor update.",
            "recommended_actions": [],
            "confidence": "LOW",
        }

        result = notify_if_needed(
            self.monitor,
            analysis,
            snapshot_id=42,
            notification_file=self.notification_file,
            send_email_fn=send_mock,
        )

        self.assertFalse(result["sent"])
        self.assertTrue(result["skipped"])
        send_mock.assert_not_called()

    def test_disabled_notification_skips(self):
        disabled_config = json.loads(
            self.notification_file.read_text(encoding="utf-8")
        )
        disabled_config["enabled"] = False
        self.notification_file.write_text(
            json.dumps(disabled_config),
            encoding="utf-8",
        )

        send_mock = MagicMock()
        result = notify_if_needed(
            self.monitor,
            {"impact_level": "HIGH"},
            snapshot_id=42,
            notification_file=self.notification_file,
            send_email_fn=send_mock,
        )

        self.assertFalse(result["sent"])
        self.assertIn("disabled", result["reason"])
        send_mock.assert_not_called()

    def test_invalid_config_handled(self):
        self.notification_file.write_text("{ invalid json", encoding="utf-8")
        send_mock = MagicMock()

        result = notify_if_needed(
            self.monitor,
            {"impact_level": "HIGH"},
            snapshot_id=42,
            notification_file=self.notification_file,
            send_email_fn=send_mock,
        )

        self.assertFalse(result["sent"])
        self.assertIn("Invalid notification config", result["reason"])
        send_mock.assert_not_called()

    def test_missing_notification_file_handled(self):
        send_mock = MagicMock()
        missing_file = Path(self.temp_dir.name) / "missing.json"

        result = notify_if_needed(
            self.monitor,
            {"impact_level": "MEDIUM"},
            snapshot_id=7,
            notification_file=missing_file,
            send_email_fn=send_mock,
        )

        self.assertFalse(result["sent"])
        send_mock.assert_not_called()

    def test_medium_triggers_email(self):
        self.assertTrue(should_notify({"impact_level": "MEDIUM"}))
        self.assertFalse(should_notify({"impact_level": "NONE"}))

    def test_build_email_content_contains_key_fields(self):
        subject, body = build_email_content(
            self.monitor,
            {
                "impact_level": "HIGH",
                "affected_modules": ["AI Features"],
                "reason": "Important change.",
                "recommended_actions": ["Assess impact"],
                "confidence": "HIGH",
            },
            snapshot_id=99,
        )

        self.assertIn("EU AI Act", subject)
        self.assertIn("Affected Modules", body)
        self.assertIn("AI Features", body)
        self.assertIn("Assess impact", body)

    def test_email_send_failure_does_not_raise(self):
        def failing_sender(*args, **kwargs):
            raise EmailSendError("SMTP unavailable")

        result = notify_if_needed(
            self.monitor,
            {"impact_level": "HIGH"},
            snapshot_id=42,
            notification_file=self.notification_file,
            send_email_fn=failing_sender,
        )

        self.assertFalse(result["sent"])
        self.assertIn("Email send failed", result["reason"])

    def test_load_notification_config_validates_required_fields(self):
        invalid_file = Path(self.temp_dir.name) / "invalid.json"
        invalid_file.write_text(json.dumps({"enabled": True}), encoding="utf-8")

        with self.assertRaises(Exception):
            load_notification_config(invalid_file)


if __name__ == "__main__":
    unittest.main()
