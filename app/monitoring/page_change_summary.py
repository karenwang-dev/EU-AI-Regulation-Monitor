from __future__ import annotations

from urllib.parse import urlparse

from app.crawler.url_normalizer import normalize_page_url


def _is_homepage_url(page_url: str, monitor_url: str) -> bool:
    return normalize_page_url(page_url) == normalize_page_url(monitor_url)


def classify_page_change_type(
    *,
    page_url: str,
    monitor_url: str,
    change_kind: str,
) -> str:
    if change_kind == "page_added":
        return "Added page"
    if change_kind == "page_removed":
        return "Removed page"
    if _is_homepage_url(page_url, monitor_url):
        return "Homepage"
    return "Child page"


def build_page_change_record(
    *,
    monitor: dict,
    page_url: str,
    page_title: str,
    before_hash: str | None,
    after_hash: str | None,
    diff_text: str,
    change_kind: str = "page_changed",
    parent_url: str | None = None,
    crawl_depth: int = 0,
) -> dict:
    monitor_url = monitor.get("url", "")
    page_type = classify_page_change_type(
        page_url=page_url,
        monitor_url=monitor_url,
        change_kind=change_kind,
    )
    return {
        "page_url": page_url,
        "normalized_url": normalize_page_url(page_url),
        "page_title": page_title,
        "parent_url": parent_url or monitor_url,
        "crawl_depth": crawl_depth,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "diff_excerpt": diff_text[:500],
        "change_kind": change_kind,
        "page_type": page_type,
        "is_homepage": page_type == "Homepage",
        "is_child_page": page_type == "Child page",
    }


def summarize_monitor_run(
    monitor: dict,
    url_results: list[dict],
    *,
    previous_urls: set[str] | None = None,
    current_urls: set[str] | None = None,
) -> dict:
    monitor_url = monitor.get("url", "")
    changed_results = [
        result
        for result in url_results
        if result.get("status") in {"analyzed", "changed"}
    ]
    added_results = [result for result in url_results if result.get("status") == "page_added"]
    removed_results = [
        result for result in url_results if result.get("status") == "page_removed"
    ]

    homepage_changed = any(
        _is_homepage_url(result.get("url", ""), monitor_url)
        for result in changed_results
    )
    child_pages_changed = sum(
        1
        for result in changed_results
        if not _is_homepage_url(result.get("url", ""), monitor_url)
    )

    pages_checked = len(url_results)
    pages_changed = len(changed_results)
    pages_added = len(added_results)
    pages_removed = len(removed_results)

    if previous_urls and current_urls is not None:
        pages_added = max(pages_added, len(current_urls - previous_urls))
        pages_removed = max(pages_removed, len(previous_urls - current_urls))

    if pages_changed == 0 and pages_added == 0 and pages_removed == 0:
        overall = "no_change"
    else:
        overall = "changed"

    return {
        "monitor_id": monitor.get("id", ""),
        "pages_checked": pages_checked,
        "pages_changed": pages_changed,
        "pages_added": pages_added,
        "pages_removed": pages_removed,
        "homepage_changed": homepage_changed,
        "child_pages_changed": child_pages_changed,
        "overall_status": overall,
    }
