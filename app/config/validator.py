from __future__ import annotations

import os
from typing import Mapping

REQUIRED_ENV_VARS = ("OPENAI_API_KEY", "FIRECRAWL_API_KEY")
OPTIONAL_ENV_VARS = ("SMTP_PASSWORD",)


def _is_set(env: Mapping[str, str], key: str) -> bool:
    return bool(str(env.get(key, "")).strip())


def validate_configuration(
    environ: Mapping[str, str] | None = None,
) -> dict:
    env = dict(os.environ if environ is None else environ)

    missing = [
        key
        for key in REQUIRED_ENV_VARS
        if not _is_set(env, key)
    ]

    warnings = [
        f"{key} is not set (optional)"
        for key in OPTIONAL_ENV_VARS
        if not _is_set(env, key)
    ]

    status = "ok" if not missing else "warning"

    return {
        "status": status,
        "missing": missing,
        "warnings": warnings,
    }
