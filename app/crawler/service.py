from datetime import datetime
from typing import Any

from firecrawl import FirecrawlApp

from app.core.config import FIRECRAWL_API_KEY


_client = FirecrawlApp(
    api_key=FIRECRAWL_API_KEY
)


def _extract_markdown(result: Any) -> str:
    markdown = getattr(result, "markdown", None)
    if markdown is not None:
        return markdown

    if isinstance(result, dict):
        return result.get("markdown", "")

    return ""


def _extract_title(result: Any, fallback: str) -> str:
    metadata = getattr(result, "metadata", None)
    if metadata is not None:
        title = getattr(metadata, "title", None)
        if title:
            return title

    if isinstance(result, dict):
        metadata_dict = result.get("metadata", {})
        if isinstance(metadata_dict, dict) and metadata_dict.get("title"):
            return metadata_dict["title"]

    return fallback


def _scrape(url: str) -> Any:
    return _client.scrape(
        url,
        formats=["markdown"]
    )


def crawl(source: dict) -> dict:
    url = source["url"]
    result = _scrape(url)

    return {
        "source_id": source["source_id"],
        "url": url,
        "title": _extract_title(result, source.get("name", "")),
        "markdown": _extract_markdown(result),
        "timestamp": datetime.now().isoformat(),
    }
