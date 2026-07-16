from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from app.crawler.link_discovery import discover_links
from app.crawler.url_ranker import rank_urls
from app.source.source_loader import (
    DEFAULT_CRAWL_MODE,
    DEFAULT_MAX_DEPTH,
    DEFAULT_MAX_PAGES,
)


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment=""))


def resolve_monitor_urls(
    monitor: dict,
    discover_links_fn=discover_links,
    rank_urls_fn=rank_urls,
) -> list[dict]:
    crawl_mode = monitor.get("crawl_mode", DEFAULT_CRAWL_MODE)
    root_url = monitor["url"]
    root_entry = {
        "url": root_url,
        "title": monitor.get("name", root_url),
        "depth": 0,
    }

    if crawl_mode != "smart":
        return [root_entry]

    max_pages = monitor.get("max_pages", DEFAULT_MAX_PAGES)
    max_depth = monitor.get("max_depth", DEFAULT_MAX_DEPTH)

    links = [root_entry]
    seen_urls = {_normalize_url(root_url)}

    if max_depth >= 1:
        discovered = discover_links_fn(
            root_url,
            monitor.get("keywords", []),
            max_depth=max_depth,
            max_pages=max_pages,
        )

        for item in discovered:
            normalized_url = _normalize_url(item["url"])
            if normalized_url in seen_urls:
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
