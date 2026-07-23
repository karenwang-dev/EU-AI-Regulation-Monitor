from __future__ import annotations

from urllib.parse import urlparse


def normalize_hostname(netloc: str) -> str:
    hostname = netloc.lower()
    if hostname.startswith("www."):
        return hostname[4:]
    return hostname


def registrable_domain(netloc: str) -> str:
    hostname = normalize_hostname(netloc)
    parts = hostname.split(".")
    if len(parts) <= 2:
        return hostname
    return ".".join(parts[-2:])


def is_same_site(url: str, seed_url: str, *, same_domain_only: bool) -> bool:
    url_host = normalize_hostname(urlparse(url).netloc)
    seed_host = normalize_hostname(urlparse(seed_url).netloc)
    if same_domain_only:
        return url_host == seed_host
    return registrable_domain(url_host) == registrable_domain(seed_host)
