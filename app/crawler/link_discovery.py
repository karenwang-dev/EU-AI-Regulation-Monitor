from __future__ import annotations

from collections import deque
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

from app.crawler.pattern_filter import is_url_allowed_for_monitor
from app.crawler.url_normalizer import normalize_page_url


SOCIAL_MEDIA_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "pinterest.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "youtube.com",
}

DOWNLOAD_EXTENSIONS = {
    ".7z",
    ".avi",
    ".bmp",
    ".csv",
    ".doc",
    ".docx",
    ".gif",
    ".gz",
    ".jpeg",
    ".jpg",
    ".json",
    ".mov",
    ".mp3",
    ".mp4",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".svg",
    ".tar",
    ".tif",
    ".tiff",
    ".webp",
    ".wmv",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
}

ALLOWED_DOWNLOAD_EXTENSIONS = {".pdf"}


class _AnchorExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._current_href: str | None = None
        self._current_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return

        attributes = {
            key.lower(): value
            for key, value in attrs
            if key is not None
        }
        href = attributes.get("href")
        if href:
            self._current_href = href.strip()
            self._current_parts = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None and data:
            self._current_parts.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None:
            return

        title = " ".join(part for part in self._current_parts if part).strip()
        if not title:
            title = self._current_href

        self.links.append((self._current_href, title))
        self._current_href = None
        self._current_parts = []


def _normalize_domain(netloc: str) -> str:
    domain = netloc.lower()
    if domain.startswith("www."):
        return domain[4:]
    return domain


def _normalize_url(url: str) -> str:
    return normalize_page_url(url)


def _fetch_html(url: str) -> str:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def _extract_links(html: str, base_url: str) -> list[tuple[str, str]]:
    parser = _AnchorExtractor()
    parser.feed(html)

    extracted: list[tuple[str, str]] = []
    for href, title in parser.links:
        absolute_url = urljoin(base_url, href)
        extracted.append((absolute_url, title))
    return extracted


def _is_disallowed_scheme(url: str) -> bool:
    scheme = urlparse(url).scheme.lower()
    return scheme in {"", "mailto", "javascript", "tel", "data"}


def _is_social_media_url(url: str) -> bool:
    domain = _normalize_domain(urlparse(url).netloc)
    return domain in SOCIAL_MEDIA_DOMAINS


def _path_extension(url: str) -> str:
    path = urlparse(url).path.lower()
    if "." not in path:
        return ""
    return "." + path.rsplit(".", 1)[-1]


def _is_download_url(url: str) -> bool:
    extension = _path_extension(url)
    if not extension:
        return False
    if extension in ALLOWED_DOWNLOAD_EXTENSIONS:
        return False
    return extension in DOWNLOAD_EXTENSIONS


def _is_same_domain(url: str, seed_domain: str) -> bool:
    return _normalize_domain(urlparse(url).netloc) == seed_domain


def _is_crawlable(url: str) -> bool:
    extension = _path_extension(url)
    if not extension:
        return True
    return extension not in DOWNLOAD_EXTENSIONS and extension not in ALLOWED_DOWNLOAD_EXTENSIONS


def _is_allowed_link(url: str, seed_domain: str) -> bool:
    if _is_disallowed_scheme(url):
        return False
    if _is_social_media_url(url):
        return False
    if not _is_same_domain(url, seed_domain):
        return False
    if _is_download_url(url):
        return False
    return True


def _matches_keywords(
    url: str,
    title: str,
    keywords: list[str],
    monitor: dict | None = None,
) -> bool:
    monitor = monitor or {}
    include_patterns = monitor.get("include_patterns") or []
    if include_patterns:
        return is_url_allowed_for_monitor(url, monitor)

    if not keywords:
        return True

    haystack = f"{url} {title}".lower()
    return any(keyword.lower() in haystack for keyword in keywords if keyword.strip())


def discover_links(
    url: str,
    keywords: list[str],
    max_depth: int = 1,
    max_pages: int = 10,
    monitor: dict | None = None,
) -> list[dict]:
    if max_depth < 1 or max_pages < 1:
        return []

    seed_domain = _normalize_domain(urlparse(url).netloc)
    seed_url = _normalize_url(url)

    queue: deque[tuple[str, int]] = deque([(seed_url, 0)])
    visited: set[str] = set()
    discovered: dict[str, dict] = {}
    pages_fetched = 0

    while queue and pages_fetched < max_pages:
        current_url, depth = queue.popleft()
        if current_url in visited:
            continue
        visited.add(current_url)

        try:
            html = _fetch_html(current_url)
        except Exception:
            continue

        pages_fetched += 1

        for link_url, link_title in _extract_links(html, current_url):
            normalized_link = _normalize_url(link_url)
            if not _is_allowed_link(normalized_link, seed_domain):
                continue
            if monitor and not is_url_allowed_for_monitor(normalized_link, monitor):
                continue

            link_depth = depth + 1
            if link_depth > max_depth:
                continue

            if _matches_keywords(normalized_link, link_title, keywords, monitor=monitor):
                existing = discovered.get(normalized_link)
                if existing is None or link_depth < existing["depth"]:
                    discovered[normalized_link] = {
                        "url": normalized_link,
                        "title": link_title,
                        "depth": link_depth,
                    }

            if link_depth < max_depth and _is_crawlable(normalized_link):
                if normalized_link not in visited:
                    queue.append((normalized_link, link_depth))

    return sorted(
        discovered.values(),
        key=lambda item: (item["depth"], item["url"]),
    )
