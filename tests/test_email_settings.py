import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.config.email_secrets import decrypt_secret, encrypt_secret
from app.config.email_settings import (
    EmailSettingsError,
    PASSWORD_MASK,
    TEST_EMAIL_BODY,
    TEST_EMAIL_SUBJECT,
    build_smtp_config,
    contains_stored_password,
    load_email_settings,
    load_email_settings_public,
    save_email_settings,
)
from app.storage.service import StorageService
from app.web.app import create_dashboard_app
from app.web.report_email_helper import contains_sensitive_secret


class TestEmailSecrets(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.key_file = Path(self.temp_dir.name) / "key.bin"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_encrypt_and_decrypt_round_trip(self):
        encrypted = encrypt_secret("app-password-123", key_file=self.key_file)
        self.assertTrue(encrypted.startswith("enc:"))
        self.assertEqual(
            decrypt_secret(encrypted, key_file=self.key_file),
            "app-password-123",
        )


class TestEmailSettingsStore(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.settings_file = base_path / "email_settings.json"
        self.key_file = base_path / "email_settings.key"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_load_config(self):
        saved = save_email_settings(
            {
                "provider": "gmail",
                "username": "admin@gmail.com",
                "password": "secret-app-password",
                "recipients": ["alice@company.com", "bob@company.com"],
            },
            settings_file=self.settings_file,
            key_file=self.key_file,
        )

        self.assertEqual(saved["provider"], "gmail")
        self.assertEqual(saved["username"], "admin@gmail.com")
        self.assertTrue(saved["password_configured"])
        self.assertEqual(saved["recipient_count"], 2)

        loaded = load_email_settings(self.settings_file, key_file=self.key_file)
        self.assertEqual(loaded["smtp_host"], "smtp.gmail.com")
        self.assertEqual(loaded["smtp_port"], 587)
        self.assertEqual(loaded["password"], "secret-app-password")
        self.assertEqual(loaded["recipients"], ["alice@company.com", "bob@company.com"])

    def test_public_load_never_returns_password(self):
        save_email_settings(
            {
                "provider": "gmail",
                "username": "admin@gmail.com",
                "password": "secret-app-password",
                "recipients": ["alice@company.com"],
            },
            settings_file=self.settings_file,
            key_file=self.key_file,
        )

        public = load_email_settings_public(
            self.settings_file,
            key_file=self.key_file,
        )
        raw = json.loads(self.settings_file.read_text(encoding="utf-8"))

        self.assertTrue(public["password_configured"])
        self.assertNotIn("password", public)
        self.assertNotIn("secret-app-password", json.dumps(public))
        self.assertNotIn("secret-app-password", raw["password"])

    def test_save_keeps_existing_password_when_blank(self):
        save_email_settings(
            {
                "provider": "gmail",
                "username": "admin@gmail.com",
                "password": "secret-app-password",
                "recipients": ["alice@company.com"],
            },
            settings_file=self.settings_file,
            key_file=self.key_file,
        )

        before = json.loads(self.settings_file.read_text(encoding="utf-8"))["password"]
        save_email_settings(
            {
                "provider": "gmail",
                "username": "admin@gmail.com",
                "password": "",
                "recipients": ["alice@company.com", "bob@company.com"],
            },
            settings_file=self.settings_file,
            key_file=self.key_file,
        )
        after = json.loads(self.settings_file.read_text(encoding="utf-8"))["password"]

        self.assertEqual(before, after)
        self.assertEqual(
            load_email_settings(self.settings_file, key_file=self.key_file)["password"],
            "secret-app-password",
        )

    def test_save_keeps_existing_password_when_mask_sent(self):
        save_email_settings(
            {
                "provider": "gmail",
                "username": "admin@gmail.com",
                "password": "secret-app-password",
                "recipients": ["alice@company.com"],
            },
            settings_file=self.settings_file,
            key_file=self.key_file,
        )

        save_email_settings(
            {
                "provider": "gmail",
                "username": "admin@gmail.com",
                "password": PASSWORD_MASK,
                "recipients": ["alice@company.com"],
            },
            settings_file=self.settings_file,
            key_file=self.key_file,
        )

        self.assertEqual(
            load_email_settings(self.settings_file, key_file=self.key_file)["password"],
            "secret-app-password",
        )

    def test_validation_requires_password_on_first_save(self):
        with self.assertRaises(EmailSettingsError):
            save_email_settings(
                {
                    "provider": "gmail",
                    "username": "admin@gmail.com",
                    "password": "",
                    "recipients": ["alice@company.com"],
                },
                settings_file=self.settings_file,
                key_file=self.key_file,
            )

    def test_validation_rejects_invalid_email(self):
        with self.assertRaises(EmailSettingsError):
            save_email_settings(
                {
                    "provider": "gmail",
                    "username": "not-an-email",
                    "password": "secret-app-password",
                    "recipients": ["alice@company.com"],
                },
                settings_file=self.settings_file,
                key_file=self.key_file,
            )

    def test_validation_rejects_duplicate_recipients(self):
        with self.assertRaises(EmailSettingsError):
            save_email_settings(
                {
                    "provider": "gmail",
                    "username": "admin@gmail.com",
                    "password": "secret-app-password",
                    "recipients": [
                        "alice@company.com",
                        "Alice@Company.com",
                    ],
                },
                settings_file=self.settings_file,
                key_file=self.key_file,
            )

    def test_validation_ignores_empty_recipient_rows(self):
        saved = save_email_settings(
            {
                "provider": "gmail",
                "username": "admin@gmail.com",
                "password": "secret-app-password",
                "recipients": ["alice@company.com", "", "   "],
            },
            settings_file=self.settings_file,
            key_file=self.key_file,
        )

        self.assertEqual(saved["recipients"], ["alice@company.com"])
        self.assertEqual(saved["recipient_count"], 1)

    def test_custom_provider_requires_host_and_port(self):
        with self.assertRaises(EmailSettingsError):
            save_email_settings(
                {
                    "provider": "custom",
                    "username": "admin@gmail.com",
                    "password": "secret-app-password",
                    "recipients": ["alice@company.com"],
                },
                settings_file=self.settings_file,
                key_file=self.key_file,
            )

    def test_build_smtp_config_for_sender(self):
        save_email_settings(
            {
                "provider": "gmail",
                "username": "admin@gmail.com",
                "password": "secret-app-password",
                "recipients": ["alice@company.com"],
            },
            settings_file=self.settings_file,
            key_file=self.key_file,
        )

        smtp_config = build_smtp_config(self.settings_file, key_file=self.key_file)
        self.assertEqual(smtp_config["smtp_host"], "smtp.gmail.com")
        self.assertEqual(smtp_config["smtp_password"], "secret-app-password")
        self.assertEqual(smtp_config["to_addresses"], ["alice@company.com"])


class TestEmailSettingsWeb(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.settings_file = base_path / "email_settings.json"
        self.key_file = base_path / "email_settings.key"
        self.reports_dir = base_path / "reports"
        self.report_config_file = base_path / "report.json"
        self.notification_file = base_path / "notification.json"

        self.report_config_file.write_text(
            json.dumps({"email_enabled": False, "recipients": []}),
            encoding="utf-8",
        )
        self.notification_file.write_text(
            json.dumps(
                {
                    "enabled": False,
                    "from_address": "monitor@example.com",
                    "to_addresses": [],
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
        self.client = TestClient(
            create_dashboard_app(
                storage_service=self.store,
                reports_dir=self.reports_dir,
                report_config_file=self.report_config_file,
                notification_file=self.notification_file,
                email_settings_file=self.settings_file,
            )
        )

    def tearDown(self):
        self.client = None
        self.temp_dir.cleanup()

    def _save_via_api(self):
        return self.client.put(
            "/api/email/settings",
            json={
                "provider": "gmail",
                "username": "admin@gmail.com",
                "password": "secret-app-password",
                "recipients": ["alice@company.com", "bob@company.com"],
            },
        )

    def test_get_settings_defaults(self):
        response = self.client.get("/api/email/settings")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["configured"])
        self.assertEqual(payload["provider"], "gmail")

    def test_save_settings_via_api(self):
        response = self._save_via_api()
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["password_configured"])
        self.assertEqual(payload["recipient_count"], 2)
        self.assertTrue(self.settings_file.exists())

    def test_reports_page_shows_email_settings_and_masks_password(self):
        self._save_via_api()
        response = self.client.get("/reports")
        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertIn("Email Settings", content)
        self.assertIn("admin@gmail.com", content)
        self.assertIn("alice@company.com", content)
        self.assertNotIn("secret-app-password", content)
        self.assertFalse(
            contains_sensitive_secret(
                content,
                email_settings_file=self.settings_file,
            )
        )

    def test_recipient_crud_via_api(self):
        self._save_via_api()
        update_response = self.client.put(
            "/api/email/settings",
            json={
                "provider": "gmail",
                "username": "admin@gmail.com",
                "password": "",
                "recipients": ["alice@company.com", "carol@company.com"],
            },
        )
        self.assertEqual(update_response.status_code, 200)
        payload = update_response.json()
        self.assertEqual(
            payload["recipients"],
            ["alice@company.com", "carol@company.com"],
        )

    def test_test_email_action_uses_settings_sender(self):
        self._save_via_api()
        send_mock = MagicMock()
        client = TestClient(
            create_dashboard_app(
                storage_service=self.store,
                reports_dir=self.reports_dir,
                report_config_file=self.report_config_file,
                notification_file=self.notification_file,
                email_settings_file=self.settings_file,
                settings_send_email_fn=send_mock,
            )
        )

        response = client.post("/api/email/settings/test")

        self.assertEqual(response.status_code, 200)
        send_mock.assert_called_once()
        self.assertEqual(send_mock.call_args.args[1], TEST_EMAIL_SUBJECT)
        self.assertEqual(send_mock.call_args.args[2], TEST_EMAIL_BODY)

    @patch.dict("os.environ", {"SMTP_PASSWORD": "legacy-gmail-password"}, clear=False)
    def test_test_email_prefers_saved_ui_settings_over_legacy_env(self):
        self.client.put(
            "/api/email/settings",
            json={
                "provider": "hisense",
                "username": "user@hisense.com",
                "password": "hisense-password",
                "recipients": ["recipient@example.com"],
            },
        )
        send_mock = MagicMock()
        client = TestClient(
            create_dashboard_app(
                storage_service=self.store,
                reports_dir=self.reports_dir,
                report_config_file=self.report_config_file,
                notification_file=self.notification_file,
                email_settings_file=self.settings_file,
                settings_send_email_fn=send_mock,
            )
        )

        response = client.post("/api/email/settings/test")

        self.assertEqual(response.status_code, 200)
        send_mock.assert_called_once()
        smtp_config = send_mock.call_args.args[0]
        self.assertEqual(smtp_config["provider"], "hisense")
        self.assertEqual(smtp_config["smtp_host"], "mail.hisense.com")
        self.assertEqual(smtp_config["smtp_port"], 465)
        self.assertTrue(smtp_config["use_ssl"])
        self.assertFalse(smtp_config["use_tls"])
        self.assertEqual(smtp_config["smtp_password"], "hisense-password")
        self.assertNotEqual(smtp_config["smtp_password"], "legacy-gmail-password")

    def test_validation_error_from_api(self):
        response = self.client.put(
            "/api/email/settings",
            json={
                "provider": "gmail",
                "username": "bad-email",
                "password": "secret-app-password",
                "recipients": ["alice@company.com"],
            },
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
