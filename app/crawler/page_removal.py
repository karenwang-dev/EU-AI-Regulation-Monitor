from __future__ import annotations

import requests

from app.core.logging import get_logger

logger = get_logger(__name__)

DELETED_STATUS_CODES = {404, 410}
REQUEST_TIMEOUT_SECONDS = 12


def verify_url_deleted(url: str) -> bool:
    """Return True only when the server responds with HTTP 404 or 410."""
    try:
        response = requests.head(
            url,
            timeout=REQUEST_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
        if response.status_code in DELETED_STATUS_CODES:
            return True
        if response.status_code == 405:
            response = requests.get(
                url,
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=True,
                stream=True,
            )
            response.close()
            return response.status_code in DELETED_STATUS_CODES
        return False
    except requests.RequestException as error:
        logger.debug(
            "Could not verify deletion for %s: %s",
            url,
            error,
        )
        return False


def classify_missing_discovered_url(url: str) -> tuple[str, str]:
    if verify_url_deleted(url):
        return (
            "page_removed",
            "Page returned HTTP 404/410 — likely removed.",
        )
    return (
        "page_not_discovered",
        "Previously monitored page was not discovered in this crawl.",
    )
