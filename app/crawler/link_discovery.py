from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

from app.crawler.discovery_constants import (
    DISCOVERY_FETCH_TIMEOUT_SECONDS,
    MAX_DISCOVERED_URLS,
    MAX_LINKS_PER_PAGE,
)
from app.crawler.discovery_models import DiscoveryResult
from app.crawler.domain_utils import is_same_site
from app.crawler.pattern_filter import is_url_allowed_for_monitor
from app.crawler.url_normalizer import normalize_page_url

BLOCKED_HOST_SUFFIXES = (
    "twitter.com",
    "facebook.com",
    "linkedin.com",
    "instagram.com",
    "youtube.com",
)

BLOCKED_EXTENSIONS = (".zip",)


@dataclass
class DiscoveryStats:
    discovery_pages_fetched: int = 0
    candidate_urls: int = 0
    skipped_by_keyword: int = 0
    skipped_by_domain: int = 0
    skipped_duplicates: int = 0
    links_truncated_per_page: int = 0
    discovery_errors: list[dict] = field(default_factory=list)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_title = ""
        self._current_text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        self._current_href = None
        self._current_title = ""
        self._current_text_parts = []
        for key, value in attrs:
            if key.lower() == "href" and value:
                self._current_href = value.strip()
            elif key.lower() == "title" and value:
                self._current_title = value.strip()

    def handle_data(self, data: str) -> None:
        if self._current_href is not None and data.strip():
            self._current_text_parts.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._current_href:
            return
        anchor_text = self._current_title or " ".join(self._current_text_parts).strip()
        self.links.append((self._current_href, anchor_text))
        self._current_href = None
        self._current_title = ""
        self._current_text_parts = []


def _fetch_html(url: str) -> str:
    response = requests.get(
        url,
        timeout=DISCOVERY_FETCH_TIMEOUT_SECONDS,
        headers={"User-Agent": "EU-AI-Regulation-Monitor/1.0"},
    )
    response.raise_for_status()
    return response.text


def _is_crawlable_href(href: str, absolute_url: str) -> bool:
    lowered = href.strip().lower()
    if lowered.startswith(("mailto:", "javascript:", "tel:")):
        return False

    parsed = urlparse(absolute_url)
    if parsed.scheme not in {"http", "https"}:
        return False

    host = parsed.netloc.lower()
    if any(host == suffix or host.endswith(f".{suffix}") for suffix in BLOCKED_HOST_SUFFIXES):
        return False

    path_lower = parsed.path.lower()
    if any(path_lower.endswith(ext) for ext in BLOCKED_EXTENSIONS):
        return False

    return True


def _matches_keywords(url: str, anchor_text: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    haystack = f"{url} {anchor_text}".lower()
    return any(keyword.lower() in haystack for keyword in keywords)


def _record_fetch_error(
    stats: DiscoveryStats,
    url: str,
    *,
    status_code: int | None = None,
    timeout: bool = False,
    exception: str | None = None,
) -> None:
    stats.discovery_errors.append(
        {
            "url": url,
            "http_status": status_code,
            "timeout": timeout,
            "exception": exception,
        }
    )


def discover_links(
    root_url: str,
    keywords: list[str] | None = None,
    *,
    max_depth: int = 0,
    max_pages: int = 1,
    monitor: dict | None = None,
) -> DiscoveryResult:
    keywords = keywords or []
    monitor = monitor or {}
    same_domain_only = bool(monitor.get("same_domain_only", True))
    stats = DiscoveryStats()
    discovered: dict[str, dict] = {}
    queue: deque[tuple[str, int]] = deque([(root_url, 0)])
    visited: set[str] = set()
    queued: set[str] = {normalize_page_url(root_url)}
    pages_fetched = 0
    max_included_depth = max(max_depth, 1)

    while queue and pages_fetched < max_pages:
        current_url, depth = queue.popleft()
        normalized_current = normalize_page_url(current_url)
        if normalized_current in visited:
            stats.skipped_duplicates += 1
            continue
        visited.add(normalized_current)

        try:
            html = _fetch_html(current_url)
        except requests.Timeout:
            _record_fetch_error(stats, current_url, timeout=True)
            continue
        except requests.HTTPError as error:
            status_code = error.response.status_code if error.response is not None else None
            _record_fetch_error(stats, current_url, status_code=status_code, exception=str(error))
            continue
        except requests.RequestException as error:
            _record_fetch_error(stats, current_url, exception=str(error))
            continue

        pages_fetched += 1
        stats.discovery_pages_fetched = pages_fetched

        parser = _LinkParser()
        parser.feed(html)

        crawlable_links_seen = 0
        for href, anchor_text in parser.links:
            absolute = urljoin(current_url, href)
            if not _is_crawlable_href(href, absolute):
                continue

            crawlable_links_seen += 1
            if crawlable_links_seen > MAX_LINKS_PER_PAGE:
                stats.links_truncated_per_page += 1
                break

            normalized_link = normalize_page_url(absolute)
            if normalized_link in discovered:
                stats.skipped_duplicates += 1
                continue

            stats.candidate_urls += 1

            if not is_same_site(
                absolute,
                root_url,
                same_domain_only=same_domain_only,
            ):
                stats.skipped_by_domain += 1
                continue

            if not is_url_allowed_for_monitor(absolute, monitor):
                continue

            keyword_match = _matches_keywords(absolute, anchor_text, keywords)
            if not keyword_match:
                stats.skipped_by_keyword += 1

            link_depth = depth + 1
            if (
                keyword_match
                and link_depth <= max_included_depth
                and len(discovered) < MAX_DISCOVERED_URLS
            ):
                discovered[normalized_link] = {
                    "url": absolute,
                    "title": anchor_text,
                    "depth": link_depth,
                    "keyword_match": True,
                }

            if depth < max_depth and len(discovered) < MAX_DISCOVERED_URLS:
                if normalized_link not in queued:
                    queued.add(normalized_link)
                    queue.append((absolute, link_depth))

    links = [
        item
        for item in discovered.values()
        if item.get("keyword_match", True)
    ]
    return DiscoveryResult(
        links=links,
        stats={
            "discovery_pages_fetched": stats.discovery_pages_fetched,
            "candidate_urls": stats.candidate_urls,
            "selected_pages": len(links),
            "skipped_by_keyword": stats.skipped_by_keyword,
            "skipped_by_domain": stats.skipped_by_domain,
            "skipped_duplicates": stats.skipped_duplicates,
            "links_truncated_per_page": stats.links_truncated_per_page,
            "discovery_errors": stats.discovery_errors,
        },
    )
