from __future__ import annotations

from urllib.parse import urljoin, urlparse

from app.crawler.link_discovery import discover_links
from app.crawler.pattern_filter import is_url_allowed_for_monitor
from app.crawler.url_normalizer import normalize_page_url
from app.crawler.url_ranker import rank_urls
from app.source.source_loader import (
    DEFAULT_CRAWL_MODE,
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_PAGES,
)


def _normalize_url(url: str) -> str:
    return normalize_page_url(url)


def _is_multipage_mode(crawl_mode: str) -> bool:
    return crawl_mode in {"smart", "multi_page"}


def _build_seed_urls(monitor: dict) -> list[dict]:
    root_url = monitor["url"]
    parsed = urlparse(root_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    seed_paths = monitor.get("seed_paths") or []

    seeds = [{"url": root_url, "title": monitor.get("name", root_url), "depth": 0}]
    seen = {_normalize_url(root_url)}

    for path in seed_paths:
        cleaned = str(path or "").strip()
        if not cleaned:
            continue
        if cleaned.startswith("http://") or cleaned.startswith("https://"):
            candidate = cleaned
        else:
            candidate = urljoin(base, cleaned)
        normalized = _normalize_url(candidate)
        if normalized in seen:
            continue
        if not is_url_allowed_for_monitor(normalized, monitor):
            continue
        seen.add(normalized)
        seeds.append(
            {
                "url": candidate,
                "title": cleaned,
                "depth": 1,
            }
        )
    return seeds


def resolve_monitor_urls(
    monitor: dict,
    discover_links_fn=discover_links,
    rank_urls_fn=rank_urls,
    *,
    local_test_urls_fn=None,
) -> list[dict]:
    crawl_mode = monitor.get("crawl_mode", DEFAULT_CRAWL_MODE)
    root_url = monitor["url"]
    root_entry = {
        "url": root_url,
        "title": monitor.get("name", root_url),
        "depth": 0,
    }

    if monitor.get("id") == "local-multipage-change-test" and local_test_urls_fn:
        return local_test_urls_fn(root_url, monitor)

    if not _is_multipage_mode(crawl_mode):
        return [root_entry]

    max_pages = monitor.get("max_pages", DEFAULT_MAX_PAGES)
    max_depth = monitor.get("max_depth", DEFAULT_MAX_DEPTH)

    links = _build_seed_urls(monitor)
    seen_urls = {_normalize_url(item["url"]) for item in links}

    if max_depth >= 1:
        discovered = discover_links_fn(
            root_url,
            monitor.get("keywords", []),
            max_depth=max_depth,
            max_pages=max_pages,
            monitor=monitor,
        )

        for item in discovered:
            normalized_url = _normalize_url(item["url"])
            if normalized_url in seen_urls:
                continue
            if not is_url_allowed_for_monitor(normalized_url, monitor):
                continue

            seen_urls.add(normalized_url)
            links.append(
                {
                    "url": item["url"],
                    "title": item.get("title", item["url"]),
                    "depth": item["depth"],
                }
            )

    ranked_links = rank_urls_fn(links, monitor)
    return ranked_links[:max_pages]
