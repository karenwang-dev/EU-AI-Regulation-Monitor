from datetime import datetime
from typing import Any

from firecrawl import FirecrawlApp

from app.core.config import FIRECRAWL_API_KEY
from app.crawler.pdf_handler import (
    PdfDownloadError,
    PdfExtractionError,
    download_pdf,
    extract_pdf_text,
    extract_pdf_title,
    is_pdf_url,
)


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


def _crawl_pdf(source: dict) -> dict:
    url = source["url"]
    fallback_title = source.get("name", "")

    pdf_path = download_pdf(url)
    markdown = extract_pdf_text(pdf_path)
    title = extract_pdf_title(pdf_path, fallback=fallback_title) or fallback_title

    return {
        "source_id": source["source_id"],
        "url": url,
        "title": title,
        "markdown": markdown,
        "timestamp": datetime.now().isoformat(),
    }


def crawl(source: dict) -> dict:
    url = source["url"]

    if is_pdf_url(url):
        try:
            return _crawl_pdf(source)
        except (PdfDownloadError, PdfExtractionError) as error:
            raise RuntimeError(str(error)) from error

    result = _scrape(url)

    return {
        "source_id": source["source_id"],
        "url": url,
        "title": _extract_title(result, source.get("name", "")),
        "markdown": _extract_markdown(result),
        "timestamp": datetime.now().isoformat(),
    }
