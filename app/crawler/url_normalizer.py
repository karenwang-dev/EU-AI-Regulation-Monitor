from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.crawler.discovery_constants import TRACKING_QUERY_PARAMS


def normalize_page_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_PARAMS
    ]
    query = urlencode(sorted(query_pairs)) if query_pairs else ""

    return urlunparse((scheme, netloc, path, "", query, ""))
