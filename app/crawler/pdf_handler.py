from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import requests
from pypdf import PdfReader, PdfWriter


class PdfDownloadError(Exception):
    pass


class PdfExtractionError(Exception):
    pass


def is_pdf_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(".pdf")


def _pdf_filename(url: str) -> str:
    filename = Path(urlparse(url).path).name
    if not filename:
        return "document.pdf"
    if not filename.lower().endswith(".pdf"):
        return f"{filename}.pdf"
    return filename


def download_pdf(
    url: str,
    download_dir: Path | None = None,
) -> Path:
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
    except requests.RequestException as error:
        raise PdfDownloadError(f"Failed to download PDF: {url}") from error

    content_type = response.headers.get("Content-Type", "").lower()
    if content_type and "pdf" not in content_type and not is_pdf_url(url):
        raise PdfDownloadError(
            f"URL did not return PDF content: {url} ({content_type})"
        )

    target_dir = Path(download_dir) if download_dir else Path("data/raw/pdfs")
    target_dir.mkdir(parents=True, exist_ok=True)

    file_path = target_dir / _pdf_filename(url)
    if file_path.exists():
        stem = file_path.stem
        suffix = file_path.suffix
        counter = 2
        while file_path.exists():
            file_path = target_dir / f"{stem}_{counter}{suffix}"
            counter += 1

    try:
        file_path.write_bytes(response.content)
    except OSError as error:
        raise PdfDownloadError(f"Failed to save PDF: {file_path}") from error

    return file_path


def extract_pdf_text(path: Path | str) -> str:
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise PdfExtractionError(f"PDF file not found: {pdf_path}")

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as error:
        raise PdfExtractionError(f"Failed to read PDF: {pdf_path}") from error

    pages: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        cleaned = page_text.strip()
        if cleaned:
            pages.append(cleaned)

    if not pages:
        return ""

    return "\n\n".join(pages)


def extract_pdf_title(path: Path | str, fallback: str = "") -> str:
    pdf_path = Path(path)
    try:
        reader = PdfReader(str(pdf_path))
        metadata = reader.metadata
        if metadata:
            title = metadata.get("/Title") or metadata.title
            if title and str(title).strip():
                return str(title).strip()
    except Exception:
        pass

    stem = pdf_path.stem.replace("_", " ").replace("-", " ").strip()
    if stem:
        return re.sub(r"\s+", " ", stem)

    return fallback
