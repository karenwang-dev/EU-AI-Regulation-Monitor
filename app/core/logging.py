from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
APP_LOG_FILE = LOG_DIR / "app.log"
ERROR_LOG_FILE = LOG_DIR / "error.log"
ROOT_LOGGER_NAME = "regulation_monitor"

_configured = False


class _ErrorOnlyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.ERROR


def _configure_logging(log_dir: Path | None = None) -> None:
    global _configured
    if _configured:
        return

    target_dir = log_dir or LOG_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger(ROOT_LOGGER_NAME)
    root_logger.setLevel(logging.INFO)
    root_logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    app_log_handler = RotatingFileHandler(
        target_dir / "app.log",
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    app_log_handler.setLevel(logging.INFO)
    app_log_handler.setFormatter(formatter)

    error_log_handler = RotatingFileHandler(
        target_dir / "error.log",
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    error_log_handler.setLevel(logging.ERROR)
    error_log_handler.addFilter(_ErrorOnlyFilter())
    error_log_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(app_log_handler)
    root_logger.addHandler(error_log_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    _configure_logging()

    if name.startswith(f"{ROOT_LOGGER_NAME}."):
        return logging.getLogger(name)

    if name == ROOT_LOGGER_NAME:
        return logging.getLogger(ROOT_LOGGER_NAME)

    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


def reset_logging_config() -> None:
    """Reset logging configuration (for tests)."""
    global _configured

    root_logger = logging.getLogger(ROOT_LOGGER_NAME)
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)

    _configured = False
