import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.logging import get_logger, reset_logging_config


class TestLogging(unittest.TestCase):

    def setUp(self):
        reset_logging_config()

    def tearDown(self):
        reset_logging_config()

    def test_get_logger_returns_named_logger(self):
        logger = get_logger("app.scheduler")
        self.assertEqual(logger.name, "regulation_monitor.app.scheduler")

    def test_info_messages_written_to_app_log(self):
        temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        try:
            log_dir = Path(temp_dir.name)
            with patch("app.core.logging.LOG_DIR", log_dir):
                reset_logging_config()
                logger = get_logger("test.info")
                logger.info("Pipeline started")
                reset_logging_config()

            app_log = log_dir / "app.log"
            self.assertTrue(app_log.exists())
            self.assertIn("Pipeline started", app_log.read_text(encoding="utf-8"))
        finally:
            temp_dir.cleanup()

    def test_error_messages_written_to_error_log(self):
        temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        try:
            log_dir = Path(temp_dir.name)
            with patch("app.core.logging.LOG_DIR", log_dir):
                reset_logging_config()
                logger = get_logger("test.error")
                logger.error("Database connection failed")
                reset_logging_config()

            error_log = log_dir / "error.log"
            self.assertTrue(error_log.exists())
            self.assertIn(
                "Database connection failed",
                error_log.read_text(encoding="utf-8"),
            )
        finally:
            temp_dir.cleanup()

    def test_error_messages_also_written_to_app_log(self):
        temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        try:
            log_dir = Path(temp_dir.name)
            with patch("app.core.logging.LOG_DIR", log_dir):
                reset_logging_config()
                logger = get_logger("test.error")
                logger.error("Scheduler job failed")
                reset_logging_config()

            app_log = log_dir / "app.log"
            self.assertIn(
                "Scheduler job failed",
                app_log.read_text(encoding="utf-8"),
            )
        finally:
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
