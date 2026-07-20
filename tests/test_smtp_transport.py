import json
import smtplib
import socket
import ssl
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.config.email_settings import (
    EmailSettingsError,
    PROVIDER_PRESETS,
    build_smtp_config,
    load_email_settings,
    save_email_settings,
)
from app.notification.email_sender import (
    EmailSendError,
    create_smtp_connection,
    humanize_smtp_error,
    log_smtp_failure,
    send_email,
    send_smtp_message,
    smtp_uses_starttls,
)
from app.report.email_sender import send_report_email


class TestSmtpTransport(unittest.TestCase):

    def _smtp_config(self, **overrides) -> dict:
        config = {
            "from_address": "sender@example.com",
            "to_addresses": ["recipient@example.com"],
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "sender@example.com",
            "smtp_password": "secret-password",
            "use_ssl": False,
            "use_tls": True,
        }
        config.update(overrides)
        return config

    @patch("app.notification.email_sender.smtplib.SMTP_SSL")
    def test_smtp_ssl_connection_uses_ssl_context(self, mock_smtp_ssl):
        mock_server = MagicMock()
        mock_smtp_ssl.return_value = mock_server

        with create_smtp_connection(self._smtp_config(smtp_port=465, use_ssl=True, use_tls=False)) as server:
            self.assertEqual(server, mock_server)

        mock_smtp_ssl.assert_called_once()
        args, kwargs = mock_smtp_ssl.call_args
        self.assertEqual(args, ("smtp.example.com", 465))
        self.assertEqual(kwargs["timeout"], 30)
        self.assertIsInstance(kwargs["context"], ssl.SSLContext)
        mock_server.quit.assert_called_once()
        mock_server.starttls.assert_not_called()

    @patch("app.notification.email_sender.smtplib.SMTP_SSL")
    def test_hisense_uses_smtp_ssl_without_starttls(self, mock_smtp_ssl):
        mock_server = MagicMock()
        mock_smtp_ssl.return_value = mock_server
        config = self._smtp_config(
            smtp_host="mail.hisense.com",
            smtp_port=465,
            use_ssl=True,
            use_tls=False,
        )

        with create_smtp_connection(config) as server:
            self.assertEqual(server, mock_server)

        mock_smtp_ssl.assert_called_once()
        args, kwargs = mock_smtp_ssl.call_args
        self.assertEqual(args, ("mail.hisense.com", 465))
        self.assertEqual(kwargs["timeout"], 30)
        self.assertIsInstance(kwargs["context"], ssl.SSLContext)
        self.assertFalse(smtp_uses_starttls(config))
        mock_server.starttls.assert_not_called()

    @patch("app.notification.email_sender.smtplib.SMTP")
    def test_starttls_connection_calls_ehlo_and_starttls(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        with create_smtp_connection(self._smtp_config()) as server:
            self.assertEqual(server, mock_server)

        mock_smtp.assert_called_once_with("smtp.example.com", 587, timeout=30)
        self.assertEqual(mock_server.ehlo.call_count, 2)
        mock_server.starttls.assert_called_once()
        self.assertIsInstance(mock_server.starttls.call_args.kwargs["context"], ssl.SSLContext)
        mock_server.quit.assert_called_once()

    @patch("app.notification.email_sender.smtplib.SMTP")
    def test_plain_smtp_does_not_call_starttls(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        with create_smtp_connection(
            self._smtp_config(use_tls=False, use_ssl=False)
        ) as server:
            self.assertEqual(server, mock_server)

        mock_server.starttls.assert_not_called()
        mock_server.ehlo.assert_not_called()

    @patch("app.notification.email_sender.create_smtp_connection")
    def test_send_email_logs_in_and_sends(self, mock_create):
        mock_server = MagicMock()
        mock_create.return_value.__enter__.return_value = mock_server
        mock_create.return_value.__exit__.return_value = False

        send_email(
            self._smtp_config(),
            "AI Regulation Monitor",
            "Test body",
        )

        mock_server.login.assert_called_once_with("sender@example.com", "secret-password")
        mock_server.sendmail.assert_called_once()

    @patch("app.notification.email_sender.create_smtp_connection")
    def test_send_report_email_uses_shared_transport(self, mock_create):
        mock_server = MagicMock()
        mock_create.return_value.__enter__.return_value = mock_server
        mock_create.return_value.__exit__.return_value = False

        send_report_email(
            {
                "title": "Weekly Regulation Monitoring Report",
                "generated_at": "2026-07-16T08:30:00",
                "period": {"start": "2026-07-09", "end": "2026-07-16"},
                "summary": {"affected_modules": []},
                "executive_summary": "Summary",
                "key_changes": [],
                "risk_summary": "Risk",
            },
            self._smtp_config(use_ssl=True, use_tls=False, smtp_port=465),
        )

        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()

    def test_humanize_timeout_error(self):
        message = humanize_smtp_error(TimeoutError("timed out"))
        self.assertIn("Unable to connect to the SMTP server", message)

    def test_humanize_gaierror(self):
        message = humanize_smtp_error(socket.gaierror("Name or service not known"))
        self.assertIn("Unable to resolve the SMTP server hostname", message)

    def test_humanize_connection_refused(self):
        message = humanize_smtp_error(ConnectionRefusedError(10061, "Connection refused"))
        self.assertIn("refused the connection", message)

    def test_humanize_ssl_cert_verification_error(self):
        message = humanize_smtp_error(
            ssl.SSLCertVerificationError("certificate verify failed")
        )
        self.assertIn("certificate verification failed", message)

    def test_humanize_ssl_error(self):
        message = humanize_smtp_error(ssl.SSLError("wrong version number"))
        self.assertIn("SSL connection failed", message)
        self.assertIn("SSL/STARTTLS mode", message)

    def test_humanize_authentication_error(self):
        message = humanize_smtp_error(
            smtplib.SMTPAuthenticationError(535, b"Authentication failed")
        )
        self.assertIn("SMTP authentication failed", message)
        self.assertIn("authorization password", message)

    def test_humanize_not_supported_error(self):
        message = humanize_smtp_error(
            smtplib.SMTPNotSupportedError("STARTTLS extension not supported by server")
        )
        self.assertIn("does not support the selected security mode", message)

    def test_humanize_cert_message_from_wrapped_email_send_error(self):
        cause = ssl.SSLCertVerificationError("certificate verify failed")
        wrapped = EmailSendError(str(cause))
        wrapped.__cause__ = cause
        message = humanize_smtp_error(wrapped)
        self.assertIn("certificate verification failed", message)

    @patch("app.notification.email_sender.logger")
    def test_log_smtp_failure_includes_connection_context(self, logger_mock):
        config = self._smtp_config(
            smtp_host="mail.hisense.com",
            smtp_port=465,
            use_ssl=True,
            use_tls=False,
        )
        error = EmailSendError("certificate verify failed")
        error.__cause__ = ssl.SSLCertVerificationError("certificate verify failed")

        log_smtp_failure(config, error)

        logger_mock.exception.assert_called_once()
        args = logger_mock.exception.call_args[0]
        self.assertIn("SSLCertVerificationError", args[1])
        self.assertEqual(args[2], "mail.hisense.com")
        self.assertEqual(args[3], 465)
        self.assertTrue(args[4])
        self.assertFalse(args[5])
        self.assertNotIn("secret-password", str(logger_mock.exception.call_args))

    @patch("app.notification.email_sender.log_smtp_failure")
    @patch("app.notification.email_sender.create_smtp_connection")
    def test_send_smtp_message_logs_before_raise(self, mock_create, log_mock):
        mock_create.side_effect = ssl.SSLError("wrong version number")
        config = self._smtp_config()

        with self.assertRaises(EmailSendError):
            send_smtp_message(
                config,
                from_address=config["from_address"],
                to_addresses=config["to_addresses"],
                message_content="test",
            )

        log_mock.assert_called_once()
        self.assertEqual(log_mock.call_args[0][0], config)

    def test_humanize_sender_rejected(self):
        message = humanize_smtp_error(
            smtplib.SMTPSenderRefused(550, b"Sender rejected", "sender@example.com")
        )
        self.assertIn("rejected the sender address", message)

    def test_humanize_recipients_rejected(self):
        message = humanize_smtp_error(
            smtplib.SMTPRecipientsRefused({"bad@example.com": (550, b"Rejected")})
        )
        self.assertIn("recipients were rejected", message)

    def test_humanize_smtp_data_error(self):
        message = humanize_smtp_error(
            smtplib.SMTPDataError(554, b"Message rejected")
        )
        self.assertIn("rejected the message content", message)

    def test_authentication_error_is_not_connection_error(self):
        message = humanize_smtp_error(
            smtplib.SMTPAuthenticationError(535, b"Authentication failed")
        )
        self.assertIn("SMTP authentication failed", message)
        self.assertNotIn("Unable to connect", message)

    @patch("app.notification.email_sender.logger")
    def test_log_smtp_connection_attempt_logs_safe_context(self, logger_mock):
        config = self._smtp_config(
            provider="hisense",
            smtp_host="mail.hisense.com",
            smtp_port=465,
            use_ssl=True,
            use_tls=False,
        )

        from app.notification.email_sender import log_smtp_connection_attempt

        log_smtp_connection_attempt(config)

        logger_mock.info.assert_called_once()
        message = logger_mock.info.call_args[0][0]
        self.assertIn("provider=%s", message)
        args = logger_mock.info.call_args[0][1:]
        self.assertEqual(args[0], "hisense")
        self.assertEqual(args[1], "mail.hisense.com")
        self.assertEqual(args[2], 465)
        self.assertTrue(args[3])
        self.assertFalse(args[4])
        self.assertTrue(args[5])
        self.assertTrue(args[6])
        self.assertNotIn("secret-password", str(logger_mock.info.call_args))


class TestEmailSettingsSslSupport(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.settings_file = base_path / "email_settings.json"
        self.key_file = base_path / "email_settings.key"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_old_settings_without_use_ssl_default_to_false(self):
        self.settings_file.write_text(
            json.dumps(
                {
                    "provider": "gmail",
                    "smtp_host": "smtp.gmail.com",
                    "smtp_port": 587,
                    "username": "admin@gmail.com",
                    "password": "enc:placeholder",
                    "recipients": ["alice@company.com"],
                    "use_tls": True,
                }
            ),
            encoding="utf-8",
        )

        with patch(
            "app.config.email_settings.decrypt_secret",
            return_value="secret-app-password",
        ):
            loaded = load_email_settings(self.settings_file, key_file=self.key_file)

        self.assertFalse(loaded["use_ssl"])
        self.assertTrue(loaded["use_tls"])

    def test_hisense_preset_uses_ssl_on_465(self):
        saved = save_email_settings(
            {
                "provider": "hisense",
                "username": "user@hisense.com",
                "password": "company-password",
                "recipients": ["recipient@example.com"],
            },
            settings_file=self.settings_file,
            key_file=self.key_file,
        )

        self.assertEqual(saved["provider"], "hisense")
        self.assertEqual(saved["smtp_host"], "mail.hisense.com")
        self.assertEqual(saved["smtp_port"], 465)
        self.assertTrue(saved["use_ssl"])
        self.assertFalse(saved["use_tls"])

    def test_gmail_preset_uses_starttls_on_587(self):
        saved = save_email_settings(
            {
                "provider": "gmail",
                "username": "admin@gmail.com",
                "password": "secret-app-password",
                "recipients": ["alice@company.com"],
            },
            settings_file=self.settings_file,
            key_file=self.key_file,
        )

        self.assertEqual(saved["smtp_port"], 587)
        self.assertFalse(saved["use_ssl"])
        self.assertTrue(saved["use_tls"])

    def test_outlook_preset_uses_office365_host(self):
        saved = save_email_settings(
            {
                "provider": "outlook",
                "username": "user@example.com",
                "password": "secret-app-password",
                "recipients": ["alice@company.com"],
            },
            settings_file=self.settings_file,
            key_file=self.key_file,
        )

        self.assertEqual(saved["smtp_host"], PROVIDER_PRESETS["outlook"]["smtp_host"])
        self.assertEqual(saved["smtp_port"], 587)
        self.assertFalse(saved["use_ssl"])
        self.assertTrue(saved["use_tls"])

    def test_custom_settings_remain_editable(self):
        saved = save_email_settings(
            {
                "provider": "custom",
                "smtp_host": "mail.custom.example.com",
                "smtp_port": 2525,
                "username": "sender@custom.example.com",
                "password": "secret-app-password",
                "recipients": ["alice@company.com"],
                "use_ssl": False,
                "use_tls": False,
            },
            settings_file=self.settings_file,
            key_file=self.key_file,
        )

        self.assertEqual(saved["smtp_host"], "mail.custom.example.com")
        self.assertEqual(saved["smtp_port"], 2525)
        self.assertFalse(saved["use_ssl"])
        self.assertFalse(saved["use_tls"])

    def test_rejects_both_ssl_and_starttls(self):
        with self.assertRaises(EmailSettingsError):
            save_email_settings(
                {
                    "provider": "custom",
                    "smtp_host": "mail.example.com",
                    "smtp_port": 465,
                    "username": "sender@example.com",
                    "password": "secret-app-password",
                    "recipients": ["alice@company.com"],
                    "use_ssl": True,
                    "use_tls": True,
                },
                settings_file=self.settings_file,
                key_file=self.key_file,
            )

    def test_rejects_invalid_port(self):
        with self.assertRaises(EmailSettingsError):
            save_email_settings(
                {
                    "provider": "custom",
                    "smtp_host": "mail.example.com",
                    "smtp_port": 70000,
                    "username": "sender@example.com",
                    "password": "secret-app-password",
                    "recipients": ["alice@company.com"],
                    "use_ssl": True,
                    "use_tls": False,
                },
                settings_file=self.settings_file,
                key_file=self.key_file,
            )

    def test_build_smtp_config_includes_use_ssl(self):
        save_email_settings(
            {
                "provider": "hisense",
                "username": "user@hisense.com",
                "password": "company-password",
                "recipients": ["recipient@example.com"],
            },
            settings_file=self.settings_file,
            key_file=self.key_file,
        )

        smtp_config = build_smtp_config(self.settings_file, key_file=self.key_file)
        self.assertTrue(smtp_config["use_ssl"])
        self.assertFalse(smtp_config["use_tls"])
        self.assertEqual(smtp_config["provider"], "hisense")


if __name__ == "__main__":
    unittest.main()
