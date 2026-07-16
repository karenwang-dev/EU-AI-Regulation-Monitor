import gc
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from app.crawler.pdf_handler import (
    PdfDownloadError,
    download_pdf,
    extract_pdf_text,
    is_pdf_url,
)
from app.crawler.service import crawl
from app.pipeline import MonitoringPipeline


def _create_sample_pdf(path: Path, text: str = "EU AI Act regulation text") -> None:
    escaped = (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET"

    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            "3 0 obj\n<< /Type /Page /Parent 2 0 R "
            "/MediaBox [0 0 612 792] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        ),
        (
            f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n"
            f"{stream}\nendstream\nendobj\n"
        ),
        (
            "5 0 obj\n<< /Type /Font /Subtype /Type1 "
            "/BaseFont /Helvetica >>\nendobj\n"
        ),
    ]

    pdf_header = "%PDF-1.4\n"
    body = ""
    xref_entries = ["0000000000 65535 f "]
    offset = len(pdf_header.encode("latin-1"))

    for obj in objects:
        xref_entries.append(f"{offset:010d} 00000 n ")
        body += obj
        offset += len(obj.encode("latin-1"))

    xref_start = offset
    xref = "xref\n0 6\n" + "\n".join(xref_entries) + "\n"
    trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n"

    path.write_bytes((pdf_header + body + xref + trailer).encode("latin-1"))


class TestPdfHandler(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        self.download_dir = Path(self.temp_dir.name) / "pdfs"

    def tearDown(self):
        gc.collect()
        self.temp_dir.cleanup()

    def test_is_pdf_url_detects_pdf_extension(self):
        self.assertTrue(is_pdf_url("https://example.com/docs/regulation.pdf"))
        self.assertTrue(is_pdf_url("https://example.com/docs/REGULATION.PDF"))
        self.assertFalse(is_pdf_url("https://example.com/docs/regulation.html"))

    def test_extract_pdf_text_reads_local_pdf(self):
        pdf_path = self.download_dir / "sample.pdf"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        _create_sample_pdf(pdf_path, "Article 1: Scope of AI regulation")

        markdown = extract_pdf_text(pdf_path)

        self.assertIn("Article 1", markdown)
        self.assertIn("AI regulation", markdown)

    @patch("app.crawler.pdf_handler.requests.get")
    def test_download_pdf_saves_file(self, mock_get):
        self.download_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = self.download_dir / "remote.pdf"
        _create_sample_pdf(pdf_path, "Downloaded regulation content")
        mock_get.return_value = MagicMock(
            status_code=200,
            headers={"Content-Type": "application/pdf"},
            content=pdf_path.read_bytes(),
            raise_for_status=MagicMock(),
        )

        saved_path = download_pdf(
            "https://example.com/regulation.pdf",
            download_dir=self.download_dir,
        )

        self.assertTrue(saved_path.exists())
        self.assertEqual(saved_path.suffix.lower(), ".pdf")
        self.assertIn("Downloaded regulation content", extract_pdf_text(saved_path))

    @patch("app.crawler.pdf_handler.requests.get")
    def test_download_pdf_raises_on_failure(self, mock_get):
        mock_get.side_effect = requests.RequestException("network error")

        with self.assertRaises(PdfDownloadError):
            download_pdf(
                "https://example.com/regulation.pdf",
                download_dir=self.download_dir,
            )


class TestCrawlerPdfPath(unittest.TestCase):

    @patch("app.crawler.service._scrape")
    @patch("app.crawler.service.download_pdf")
    @patch("app.crawler.service.extract_pdf_text")
    @patch("app.crawler.service.extract_pdf_title")
    def test_crawl_uses_pdf_handler_for_pdf_urls(
        self,
        mock_extract_title,
        mock_extract_text,
        mock_download_pdf,
        mock_scrape,
    ):
        mock_download_pdf.return_value = Path("data/raw/pdfs/regulation.pdf")
        mock_extract_text.return_value = "# EU AI Act PDF\n\nRegulation text."
        mock_extract_title.return_value = "EU AI Act PDF"

        source = {
            "source_id": "eu_ai_act",
            "name": "EU AI Act",
            "url": "https://example.com/regulation.pdf",
        }

        result = crawl(source)

        mock_scrape.assert_not_called()
        mock_download_pdf.assert_called_once_with(source["url"])
        mock_extract_text.assert_called_once()
        self.assertEqual(result["source_id"], "eu_ai_act")
        self.assertEqual(result["url"], source["url"])
        self.assertEqual(result["title"], "EU AI Act PDF")
        self.assertEqual(result["markdown"], "# EU AI Act PDF\n\nRegulation text.")
        self.assertIn("T", result["timestamp"])

    @patch("app.crawler.service._scrape")
    def test_crawl_uses_firecrawl_for_non_pdf_urls(self, mock_scrape):
        mock_scrape.return_value = {
            "markdown": "# HTML regulation page",
            "metadata": {"title": "HTML Regulation"},
        }

        source = {
            "source_id": "eu_ai_act",
            "name": "EU AI Act",
            "url": "https://example.com/regulation",
        }

        result = crawl(source)

        mock_scrape.assert_called_once_with(source["url"])
        self.assertEqual(result["markdown"], "# HTML regulation page")
        self.assertEqual(result["title"], "HTML Regulation")


class TestPipelinePdfPath(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        base_path = Path(self.temp_dir.name)
        from app.storage.service import StorageService

        self.store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )

    def tearDown(self):
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    @patch("app.crawler.service.download_pdf")
    @patch("app.crawler.service.extract_pdf_text")
    @patch("app.crawler.service.extract_pdf_title")
    def test_pipeline_processes_pdf_url(
        self,
        mock_extract_title,
        mock_extract_text,
        mock_download_pdf,
    ):
        pdf_path = Path(self.temp_dir.name) / "regulation.pdf"
        _create_sample_pdf(pdf_path, "Pipeline PDF regulation content")
        mock_download_pdf.return_value = pdf_path
        mock_extract_text.return_value = "Pipeline PDF regulation content"
        mock_extract_title.return_value = "EU AI Act PDF"

        pipeline = MonitoringPipeline(
            save_snapshot_fn=self.store.save_snapshot,
            get_latest_snapshot_for_url_fn=lambda source_id, url: None,
            get_crawl_cache_fn=lambda url: None,
            update_crawl_cache_fn=lambda url, snapshot_id, content_hash: {},
            get_snapshot_by_id_fn=self.store.get_snapshot_by_id,
            analyze_change_impact_fn=MagicMock(),
            save_analysis_fn=self.store.save_analysis,
            notify_if_needed_fn=MagicMock(
                return_value={"sent": False, "skipped": True, "reason": "test"}
            ),
            should_crawl_fn=lambda url, frequency: True,
        )

        result = pipeline.process_source(
            {
                "id": "eu_ai_act",
                "name": "EU AI Act",
                "enabled": True,
                "url": "https://example.com/regulation.pdf",
                "keywords": ["AI Act"],
                "category": "AI Regulation",
                "frequency": "daily",
                "crawl_mode": "single",
            }
        )

        self.assertEqual(result["status"], "first_snapshot")
        self.assertIn("First snapshot captured", result["message"])
        snapshot = self.store.get_latest_snapshot("eu_ai_act")
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["url"], "https://example.com/regulation.pdf")
        self.assertEqual(snapshot["title"], "EU AI Act PDF")
        saved_markdown = Path(snapshot["file_path"]).read_text(encoding="utf-8")
        self.assertIn("Pipeline PDF regulation content", saved_markdown)


if __name__ == "__main__":
    unittest.main()
