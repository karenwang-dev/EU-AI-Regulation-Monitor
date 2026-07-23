import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from fastapi.testclient import TestClient

from app.crawler.discovery_constants import MAX_DISCOVERED_URLS, MAX_LINKS_PER_PAGE
from app.crawler.domain_utils import is_same_site
from app.crawler.link_discovery import discover_links
from app.crawler.url_normalizer import normalize_page_url
from app.monitors.repository import MonitorRepository, reset_monitor_repository
from app.monitors.run_store import MonitorRunStore, reset_monitor_run_store
from app.monitors.smart_discovery import validate_smart_discovery_config
from app.storage.service import StorageService
from app.web.app import create_dashboard_app


ROOT_HTML = """
<html><body>
<a href="/child-one">Child One</a>
<a href="/child-two">Child Two</a>
</body></html>
"""

NESTED_HTML = """
<html><body>
<a href="/nested">Nested Page</a>
</body></html>
"""


class TestSmartDiscoveryValidation(unittest.TestCase):
    def test_validate_smart_requires_depth_and_pages(self):
        errors = validate_smart_discovery_config(
            {"crawl_mode": "smart", "max_depth": 0, "max_pages": 1}
        )
        self.assertIn("Smart Discovery requires max_depth >= 1.", errors)
        self.assertIn(
            "Smart Discovery requires max_pages >= 2 (homepage counts as one monitored page).",
            errors,
        )

    def test_validate_smart_passes_with_defaults(self):
        errors = validate_smart_discovery_config(
            {"crawl_mode": "smart", "max_depth": 2, "max_pages": 10}
        )
        self.assertEqual(errors, [])


class TestSmartDiscoveryLimits(unittest.TestCase):
    @patch("app.crawler.link_discovery._fetch_html")
    def test_max_links_per_page(self, mock_fetch):
        links = "".join(
            f'<a href="/page-{index}">Page {index}</a>'
            for index in range(MAX_LINKS_PER_PAGE + 5)
        )
        mock_fetch.side_effect = lambda url: (
            f"<html><body>{links}</body></html>"
            if url == "https://example.com/"
            else "<html></html>"
        )

        result = discover_links(
            "https://example.com/",
            keywords=["Page"],
            max_depth=1,
            max_pages=5,
        )

        self.assertLessEqual(len(result.links), MAX_LINKS_PER_PAGE)

    @patch("app.crawler.link_discovery._fetch_html")
    def test_max_discovered_urls(self, mock_fetch):
        def build_page(index: int) -> str:
            return f"<html><body><a href='/page-{index + 1}'>Page {index + 1}</a></body></html>"

        def fetch(url: str) -> str:
            if url == "https://example.com/":
                return build_page(0)
            for index in range(MAX_DISCOVERED_URLS + 10):
                if url == f"https://example.com/page-{index}":
                    return build_page(index)
            return "<html></html>"

        mock_fetch.side_effect = fetch

        result = discover_links(
            "https://example.com/",
            keywords=["Page"],
            max_depth=3,
            max_pages=MAX_DISCOVERED_URLS + 10,
        )

        self.assertLessEqual(len(result.links), MAX_DISCOVERED_URLS)


class TestSmartDiscoveryFailureLogging(unittest.TestCase):
    @patch("app.crawler.link_discovery._fetch_html")
    def test_fetch_errors_are_recorded(self, mock_fetch):
        def fetch(url: str) -> str:
            if url == "https://example.com/":
                return ROOT_HTML
            if url.endswith("child-one"):
                raise requests.HTTPError(response=MagicMock(status_code=404))
            raise requests.Timeout("timed out")

        mock_fetch.side_effect = fetch

        result = discover_links(
            "https://example.com/",
            keywords=["Child", "Nested"],
            max_depth=2,
            max_pages=5,
        )

        self.assertGreaterEqual(len(result.stats["discovery_errors"]), 1)
        self.assertTrue(result.links)


class TestTrackingParameterCleanup(unittest.TestCase):
    def test_tracking_params_removed_before_dedup(self):
        cleaned = normalize_page_url(
            "https://example.com/page?utm_source=newsletter&id=42&page=2"
        )
        self.assertIn("id=42", cleaned)
        self.assertIn("page=2", cleaned)
        self.assertNotIn("utm_source", cleaned)

        duplicate = normalize_page_url(
            "https://example.com/page?utm_campaign=spring&id=42&page=2"
        )
        self.assertEqual(cleaned, duplicate)


class TestSameDomainOption(unittest.TestCase):
    def test_same_domain_only_requires_exact_hostname(self):
        self.assertTrue(
            is_same_site(
                "https://www.example.com/page",
                "https://example.com/",
                same_domain_only=True,
            )
        )
        self.assertFalse(
            is_same_site(
                "https://sub.example.com/page",
                "https://example.com/",
                same_domain_only=True,
            )
        )

    def test_same_domain_only_false_allows_subdomains(self):
        self.assertTrue(
            is_same_site(
                "https://sub.example.com/page",
                "https://example.com/",
                same_domain_only=False,
            )
        )


class TestDiscoverySummaryPersistence(unittest.TestCase):
    def test_save_and_load_discovery_summary(self):
        temp_dir = tempfile.TemporaryDirectory()
        try:
            store = MonitorRunStore(db_path=Path(temp_dir.name) / "runs.db")
            summary = {
                "homepage_url": "https://example.com/",
                "discovery_pages_fetched": 3,
                "candidate_urls": 12,
                "selected_pages": 2,
                "skipped_by_keyword": 1,
                "skipped_by_domain": 2,
                "skipped_duplicates": 1,
                "discovery_errors": [],
            }
            run_id = store.save_run(
                monitor_id="demo",
                monitor_name="Demo",
                triggered_by="manual",
                execution_status="success",
                change_status="unchanged",
                started_at="2026-07-20T08:00:00+00:00",
                finished_at="2026-07-20T08:00:10+00:00",
                duration_ms=10000,
                pages_checked=2,
                pages_changed=0,
                homepage_changed=False,
                child_pages_changed=0,
                discovery_summary=summary,
            )
            loaded = store.get_run(run_id)
            assert loaded is not None
            self.assertEqual(loaded["discovery_summary"], summary)
        finally:
            reset_monitor_run_store()
            temp_dir.cleanup()


class TestSmartDiscoveryApiValidation(unittest.TestCase):
    def test_create_smart_monitor_with_invalid_defaults_returns_400(self):
        temp_dir = tempfile.TemporaryDirectory()
        try:
            base_path = Path(temp_dir.name)
            db_path = base_path / "storage.db"
            monitors_file = base_path / "monitors.json"
            monitors_file.write_text(json.dumps({"monitors": []}), encoding="utf-8")
            repository = MonitorRepository(db_path=db_path, seed_file=monitors_file)
            storage = StorageService(
                db_path=db_path,
                raw_dir=base_path / "raw",
                meta_file=base_path / "snapshots.json",
            )
            with TestClient(
                create_dashboard_app(
                    storage_service=storage,
                    monitors_repository=repository,
                )
            ) as client:
                response = client.post(
                    "/api/monitors",
                    json={
                        "name": "Smart Demo",
                        "url": "https://example.com/",
                        "keywords": ["AI"],
                        "category": "AI Regulation",
                        "frequency": "daily",
                        "enabled": True,
                        "crawl_mode": "smart",
                        "max_depth": 0,
                        "max_pages": 1,
                    },
                )

            self.assertEqual(response.status_code, 400)
            self.assertIn("max_depth >= 1", response.json()["detail"])
        finally:
            reset_monitor_repository()
            reset_monitor_run_store()
            temp_dir.cleanup()


class TestRunDetailsDiscoverySummary(unittest.TestCase):
    def test_run_details_page_shows_discovery_summary(self):
        summary = {
            "homepage_url": "https://environment.ec.europa.eu/",
            "discovery_pages_fetched": 8,
            "candidate_urls": 63,
            "selected_pages": 10,
            "skipped_by_keyword": 27,
            "skipped_by_domain": 19,
            "skipped_duplicates": 7,
            "discovery_errors": [],
        }
        run_store = MagicMock()
        run_store.get_run.return_value = {
            "run_history_id": 42,
            "monitor_name": "EU Environment",
            "triggered_by": "manual",
            "execution_status": "success",
            "change_status": "unchanged",
            "started_at": "2026-07-20T08:00:00+00:00",
            "finished_at": "2026-07-20T08:00:10+00:00",
            "duration_ms": 10000,
            "pages_checked": 10,
            "pages_changed": 0,
            "homepage_changed": False,
            "child_pages_changed": 0,
            "pages_failed": 0,
            "error": None,
            "page_results": [],
            "discovery_summary": summary,
            "page_details_available": False,
        }

        app = create_dashboard_app()
        with patch("app.web.app.get_monitor_run_store", return_value=run_store):
            with TestClient(app) as client:
                response = client.get("/runs/42")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Discovery Summary", response.text)
        self.assertIn("Candidate URLs", response.text)
        self.assertIn("https://environment.ec.europa.eu/", response.text)


if __name__ == "__main__":
    unittest.main()
