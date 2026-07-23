from __future__ import annotations

from app.crawler.discovery_models import ResolveResult, empty_discovery_summary
from app.crawler.link_discovery import discover_links
from app.crawler.url_normalizer import normalize_page_url
from app.crawler.url_ranker import rank_urls


def resolve_monitor_urls(
    source: dict,
    *,
    discover_links_fn=discover_links,
    rank_urls_fn=rank_urls,
) -> ResolveResult:
    crawl_mode = source.get("crawl_mode", "single")
    root_url = source["url"]
    max_depth = int(source.get("max_depth", 0))
    max_pages = int(source.get("max_pages", 1))
    keywords = source.get("keywords") or []

    if crawl_mode in {"smart", "multi_page"}:
        discovery = discover_links_fn(
            root_url,
            keywords,
            max_depth=max_depth,
            max_pages=max_pages,
            monitor=source,
        )
        if hasattr(discovery, "links"):
            discovered_links = discovery.links
            discovery_stats = discovery.stats
        else:
            discovered_links = discovery
            discovery_stats = {}

        candidates = [
            {
                "url": root_url,
                "title": source.get("name") or root_url,
                "depth": 0,
            }
        ]
        seen = {normalize_page_url(root_url)}
        for link in discovered_links:
            normalized = normalize_page_url(link["url"])
            if normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(link)

        ranked_links = rank_urls_fn(candidates, source)
        selected = ranked_links[:max_pages]

        summary = {
            **empty_discovery_summary(root_url, crawl_mode),
            **discovery_stats,
            "selected_pages": len(selected),
        }
        return ResolveResult(urls=selected, discovery_summary=summary)

    single_url = rank_urls_fn(
        [
            {
                "url": root_url,
                "title": source.get("name") or root_url,
                "depth": 0,
            }
        ],
        source,
    )
    return ResolveResult(
        urls=single_url,
        discovery_summary={
            **empty_discovery_summary(root_url, crawl_mode),
            "selected_pages": 1,
        },
    )
