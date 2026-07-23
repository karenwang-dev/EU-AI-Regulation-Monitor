from __future__ import annotations

from dataclasses import dataclass, field


def empty_discovery_summary(homepage_url: str = "", crawl_mode: str = "single") -> dict:
    return {
        "homepage_url": homepage_url,
        "crawl_mode": crawl_mode,
        "discovery_pages_fetched": 0,
        "candidate_urls": 0,
        "selected_pages": 0,
        "skipped_by_keyword": 0,
        "skipped_by_domain": 0,
        "skipped_duplicates": 0,
        "discovery_errors": [],
    }


@dataclass
class DiscoveryResult:
    links: list[dict] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


@dataclass
class ResolveResult:
    urls: list[dict]
    discovery_summary: dict

    def __len__(self) -> int:
        return len(self.urls)

    def __iter__(self):
        return iter(self.urls)

    def __getitem__(self, index):
        return self.urls[index]
