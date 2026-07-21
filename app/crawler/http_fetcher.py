from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urlparse

import requests


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if lowered in {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if lowered in {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self._parts.append(text)

    def get_text(self) -> str:
        return "\n".join(part for part in self._parts if part).strip()


def _extract_title(html: str, fallback: str) -> str:
    lowered = html.lower()
    start = lowered.find("<title>")
    end = lowered.find("</title>")
    if start == -1 or end == -1 or end <= start:
        return fallback
    return html[start + 7 : end].strip() or fallback


def html_to_markdown(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()


def should_use_http_fetch(url: str, monitor: dict | None = None) -> bool:
    monitor = monitor or {}
    if str(monitor.get("fetch_mode", "")).strip().lower() == "http":
        return True

    host = urlparse(url).netloc.lower()
    return host.startswith("127.0.0.1") or host.startswith("localhost")


def fetch_http_page(url: str, *, fallback_title: str = "") -> dict:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    html = response.text
    return {
        "title": _extract_title(html, fallback_title or url),
        "markdown": html_to_markdown(html),
    }
