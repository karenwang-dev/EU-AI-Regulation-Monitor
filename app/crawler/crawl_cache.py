from __future__ import annotations

from datetime import datetime, timedelta

from app.storage.service import get_crawl_cache
from app.utils.datetime_utils import parse_datetime, utc_now


FREQUENCY_TTL_DAYS = {
    "daily": 1,
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
}


def should_crawl(
    url: str,
    frequency: str,
    get_cache_fn=get_crawl_cache,
    now: datetime | None = None,
) -> bool:
    cache_entry = get_cache_fn(url)
    if cache_entry is None:
        return True

    ttl_days = FREQUENCY_TTL_DAYS.get(frequency)
    if ttl_days is None:
        return True

    reference_time = now or utc_now()
    last_crawled_at = parse_datetime(cache_entry["last_crawled_at"])
    if last_crawled_at is None:
        return True
    return reference_time - last_crawled_at >= timedelta(days=ttl_days)
