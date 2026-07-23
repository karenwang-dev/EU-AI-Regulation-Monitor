from typing import Any
from urllib.parse import urlparse

from app.utils.datetime_utils import utc_now_iso

from firecrawl import FirecrawlApp

from app.core.config import FIRECRAWL_API_KEY
from app.crawler.content_cleaner import clean_monitor_content
from app.crawler.http_fetcher import fetch_http_page, should_use_http_fetch
from app.crawler.pdf_handler import (
    PdfDownloadError,
    PdfExtractionError,
    download_pdf,
    extract_pdf_text,
    extract_pdf_title,
    is_pdf_url,
)
from app.dev.change_test_site import (
    LOCAL_TEST_MONITOR_ID,
    render_page_markdown,
    resolve_page_metadata,
)
from app.crawler.url_normalizer import normalize_page_url


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


def _url_slug(url: str) -> str:
    parsed = urlparse(url)
    slug = (parsed.path or "root").strip("/").replace("/", "_") or "root"
    if parsed.query:
        slug = f"{slug}_{parsed.query.replace('=', '_').replace('&', '_')}"
    return slug[:80]


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
        "timestamp": utc_now_iso(),
    }


def _finalize_crawl_result(source: dict, *, title: str, markdown: str) -> dict:
    monitor = source.get("monitor") or {}
    cleaned_markdown = clean_monitor_content(markdown, monitor)
    target_url = source["url"]
    return {
        "source_id": source["source_id"],
        "url": target_url,
        "normalized_url": normalize_page_url(target_url),
        "title": title,
        "markdown": cleaned_markdown,
        "raw_markdown": markdown,
        "timestamp": utc_now_iso(),
        "crawl_depth": source.get("discovered_depth", 0),
        "parent_url": source.get("parent_url") or monitor.get("url"),
        "url_slug": _url_slug(target_url),
    }


def _crawl_local_change_test_site(source: dict) -> dict:
    url = source["url"]
    parsed = urlparse(url)
    path = parsed.path or "/dev/change-test-site"
    monitor = source.get("monitor") or {}
    state_file = monitor.get("_change_test_state_file")
    markdown = render_page_markdown(path, state_file=state_file)
    metadata = resolve_page_metadata(path, state_file=state_file)
    return _finalize_crawl_result(
        source,
        title=metadata["title"],
        markdown=markdown,
    )


def crawl(source: dict) -> dict:
    url = source["url"]
    monitor = source.get("monitor") or {}

    if monitor.get("id") == LOCAL_TEST_MONITOR_ID:
        return _crawl_local_change_test_site(source)

    if is_pdf_url(url):
        try:
            return _crawl_pdf(source)
        except (PdfDownloadError, PdfExtractionError) as error:
            raise RuntimeError(str(error)) from error

    if should_use_http_fetch(url, monitor):
        fetched = fetch_http_page(url, fallback_title=source.get("name", ""))
        return _finalize_crawl_result(
            source,
            title=fetched["title"],
            markdown=fetched["markdown"],
        )

    result = _scrape(url)
    return _finalize_crawl_result(
        source,
        title=_extract_title(result, source.get("name", "")),
        markdown=_extract_markdown(result),
    )
