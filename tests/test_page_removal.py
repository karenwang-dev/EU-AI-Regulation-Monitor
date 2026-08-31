import unittest
from unittest.mock import MagicMock, patch

from app.crawler.page_removal import classify_missing_discovered_url


class TestPageRemovalClassification(unittest.TestCase):

    @patch("app.crawler.page_removal.verify_url_deleted", return_value=False)
    def test_missing_discovery_is_not_removed(self, _mock_verify):
        status, message = classify_missing_discovered_url(
            "https://example.com/old-page"
        )
        self.assertEqual(status, "page_not_discovered")
        self.assertIn("not discovered", message.lower())

    @patch("app.crawler.page_removal.verify_url_deleted", return_value=True)
    def test_confirmed_http_404_is_removed(self, _mock_verify):
        status, message = classify_missing_discovered_url(
            "https://example.com/deleted-page"
        )
        self.assertEqual(status, "page_removed")
        self.assertIn("404/410", message)


if __name__ == "__main__":
    unittest.main()
