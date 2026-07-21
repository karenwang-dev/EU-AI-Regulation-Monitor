from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
from app.source.source_loader import MONITORS_FILE
from app.storage.service import DB_PATH, META_FILE, RAW_DIR

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CHANGE_TEST_SITE_FILE = PROJECT_ROOT / "data" / "change_test_site.json"


def get_default_monitor_db_path() -> Path:
    return (PROJECT_ROOT / DB_PATH).resolve()


def get_runtime_paths() -> dict[str, Path]:
    return {
        "project_root": PROJECT_ROOT,
        "database": get_default_monitor_db_path(),
        "raw_dir": (PROJECT_ROOT / RAW_DIR).resolve(),
        "snapshots_meta": (PROJECT_ROOT / META_FILE).resolve(),
        "monitors_config_seed": (PROJECT_ROOT / MONITORS_FILE).resolve(),
        "monitors_repository": get_default_monitor_db_path(),
        "change_test_site_state": CHANGE_TEST_SITE_FILE.resolve(),
    }


def log_runtime_paths(prefix: str = "") -> None:
    label = f"{prefix} " if prefix else ""
    for name, path in get_runtime_paths().items():
        logger.info("%sruntime path %s=%s", label, name, path)
