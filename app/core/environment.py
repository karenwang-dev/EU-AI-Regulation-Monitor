from __future__ import annotations

import os


def get_app_env() -> str:
    return str(os.getenv("APP_ENV", "production")).strip().lower()


def is_development() -> bool:
    return get_app_env() in {"development", "dev", "test"}


def is_production() -> bool:
    return not is_development()
