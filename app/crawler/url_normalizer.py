from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


def normalize_page_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    query = urlencode(sorted(query_pairs)) if query_pairs else ""

    return urlunparse((scheme, netloc, path, "", query, ""))
