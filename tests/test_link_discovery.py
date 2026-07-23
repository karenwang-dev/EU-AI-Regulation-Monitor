import unittest
from unittest.mock import patch

import requests

from app.crawler.link_discovery import discover_links


ROOT_HTML = """
<html>
  <head><title>Regulation Portal</title></head>
  <body>
    <a href="/policies/ai-act">EU AI Act Policy</a>
    <a href="https://example.com/policies/cybersecurity">Cybersecurity Rules</a>
    <a href="https://other-site.com/external">External Regulation</a>
    <a href="mailto:info@example.com">Email Us</a>
    <a href="javascript:void(0)">Click Me</a>
    <a href="https://twitter.com/example/status/1">Twitter Share</a>
    <a href="/downloads/report.zip">Download ZIP</a>
    <a href="/downloads/guidance.pdf">Guidance PDF</a>
    <a href="/about">About Portal</a>
  </body>
</html>
"""

NESTED_HTML = """
<html>
  <body>
    <a href="/policies/nested-ai">Nested AI Regulation</a>
    <a href="/general/news">General News</a>
  </body>
</html>
"""


class TestLinkDiscovery(unittest.TestCase):

    def _mock_fetch(self, pages: dict[str, str]):
        def fetch(url: str) -> str:
            return pages.get(url, "<html></html>")

        return fetch

    @patch("app.crawler.link_discovery._fetch_html")
    def test_discover_links_filters_by_keywords_and_domain(self, mock_fetch):
        mock_fetch.side_effect = self._mock_fetch(
            {
                "https://example.com/": ROOT_HTML,
            }
        )

        results = discover_links(
            "https://example.com/",
            keywords=["AI", "cybersecurity", "pdf"],
            max_depth=1,
            max_pages=10,
        )

        urls = {item["url"] for item in results.links}
        self.assertIn("https://example.com/policies/ai-act", urls)
        self.assertIn("https://example.com/policies/cybersecurity", urls)
        self.assertIn("https://example.com/downloads/guidance.pdf", urls)
        self.assertNotIn("https://other-site.com/external", urls)
        self.assertNotIn("mailto:info@example.com", urls)
        self.assertNotIn("https://example.com/downloads/report.zip", urls)

    @patch("app.crawler.link_discovery._fetch_html")
    def test_discover_links_returns_expected_shape(self, mock_fetch):
        mock_fetch.side_effect = self._mock_fetch(
            {
                "https://example.com/": ROOT_HTML,
            }
        )

        results = discover_links(
            "https://example.com/",
            keywords=["AI Act"],
            max_depth=1,
            max_pages=10,
        )

        self.assertEqual(len(results.links), 1)
        self.assertEqual(results.links[0]["url"], "https://example.com/policies/ai-act")
        self.assertEqual(results.links[0]["title"], "EU AI Act Policy")
        self.assertEqual(results.links[0]["depth"], 1)

    @patch("app.crawler.link_discovery._fetch_html")
    def test_discover_links_excludes_social_and_javascript_links(self, mock_fetch):
        mock_fetch.side_effect = self._mock_fetch(
            {
                "https://example.com/": ROOT_HTML,
            }
        )

        results = discover_links(
            "https://example.com/",
            keywords=["Twitter", "Click", "Email"],
            max_depth=1,
            max_pages=10,
        )

        self.assertEqual(results.links, [])

    @patch("app.crawler.link_discovery._fetch_html")
    def test_discover_links_respects_depth_limit(self, mock_fetch):
        mock_fetch.side_effect = self._mock_fetch(
            {
                "https://example.com/": ROOT_HTML,
                "https://example.com/about": NESTED_HTML,
            }
        )

        depth_one = discover_links(
            "https://example.com/",
            keywords=["AI", "Nested", "News"],
            max_depth=1,
            max_pages=10,
        )
        depth_one_urls = {item["url"] for item in depth_one.links}
        self.assertIn("https://example.com/policies/ai-act", depth_one_urls)
        self.assertNotIn("https://example.com/policies/nested-ai", depth_one_urls)

        depth_two = discover_links(
            "https://example.com/",
            keywords=["AI", "Nested", "News"],
            max_depth=2,
            max_pages=10,
        )
        depth_two_urls = {item["url"] for item in depth_two.links}
        self.assertIn("https://example.com/policies/nested-ai", depth_two_urls)
        self.assertEqual(
            next(item for item in depth_two.links if item["url"].endswith("nested-ai"))["depth"],
            2,
        )

    @patch("app.crawler.link_discovery._fetch_html")
    def test_discover_links_depth_zero_only_discovers_from_homepage(self, mock_fetch):
        mock_fetch.side_effect = self._mock_fetch(
            {
                "https://example.com/": ROOT_HTML,
                "https://example.com/about": NESTED_HTML,
            }
        )

        results = discover_links(
            "https://example.com/",
            keywords=["AI", "Nested", "News"],
            max_depth=0,
            max_pages=10,
        )

        self.assertEqual(mock_fetch.call_count, 1)
        urls = {item["url"] for item in results.links}
        self.assertIn("https://example.com/policies/ai-act", urls)
        self.assertNotIn("https://example.com/policies/nested-ai", urls)

    @patch("app.crawler.link_discovery._fetch_html")
    def test_discover_links_depth_one_includes_first_level_only(self, mock_fetch):
        mock_fetch.side_effect = self._mock_fetch(
            {
                "https://example.com/": ROOT_HTML,
                "https://example.com/about": NESTED_HTML,
            }
        )

        results = discover_links(
            "https://example.com/",
            keywords=["AI", "Nested", "News"],
            max_depth=1,
            max_pages=10,
        )

        urls = {item["url"] for item in results.links}
        self.assertIn("https://example.com/policies/ai-act", urls)
        self.assertNotIn("https://example.com/policies/nested-ai", urls)

    @patch("app.crawler.link_discovery._fetch_html")
    def test_discover_links_respects_max_pages(self, mock_fetch):
        mock_fetch.side_effect = self._mock_fetch(
            {
                "https://example.com/": ROOT_HTML,
                "https://example.com/about": NESTED_HTML,
            }
        )

        results = discover_links(
            "https://example.com/",
            keywords=["AI", "Nested", "News", "About"],
            max_depth=2,
            max_pages=1,
        )

        self.assertEqual(mock_fetch.call_count, 1)
        urls = {item["url"] for item in results.links}
        self.assertIn("https://example.com/policies/ai-act", urls)
        self.assertNotIn("https://example.com/policies/nested-ai", urls)

    @patch("app.crawler.link_discovery._fetch_html")
    def test_discover_links_allows_pdf_downloads(self, mock_fetch):
        mock_fetch.side_effect = self._mock_fetch(
            {
                "https://example.com/": ROOT_HTML,
            }
        )

        results = discover_links(
            "https://example.com/",
            keywords=["Guidance"],
            max_depth=1,
            max_pages=10,
        )

        pdf = results.links[0]
        self.assertEqual(pdf["url"], "https://example.com/downloads/guidance.pdf")
        self.assertEqual(pdf["title"], "Guidance PDF")

    @patch("app.crawler.link_discovery._fetch_html")
    def test_discover_links_handles_fetch_errors(self, mock_fetch):
        def fetch(url: str) -> str:
            if url == "https://example.com/":
                return ROOT_HTML
            raise requests.RequestException("network failure")

        mock_fetch.side_effect = fetch

        results = discover_links(
            "https://example.com/",
            keywords=["AI", "Nested"],
            max_depth=2,
            max_pages=10,
        )

        urls = {item["url"] for item in results.links}
        self.assertIn("https://example.com/policies/ai-act", urls)
        self.assertNotIn("https://example.com/policies/nested-ai", urls)


if __name__ == "__main__":
    unittest.main()
