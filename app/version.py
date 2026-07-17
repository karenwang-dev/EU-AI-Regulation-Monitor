"""Application version for display and documentation."""

from pathlib import Path

APP_NAME = "AI Regulation Monitor"

_VERSION_FILE = Path(__file__).resolve().parents[1] / "VERSION"


def _read_version() -> str:
    if not _VERSION_FILE.exists():
        return "dev"
    return _VERSION_FILE.read_text(encoding="utf-8").strip()


APP_VERSION = _read_version()
