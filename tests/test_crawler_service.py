import unittest
from unittest.mock import MagicMock, patch

from app.crawler.service import crawl


class CrawlResult:
    def __init__(self, markdown: str, title: str):
        self.markdown = markdown
        self.metadata = MagicMock(title=title)


class TestCrawlerService(unittest.TestCase):

    @patch("app.crawler.service._scrape")
    def test_crawl_returns_unified_result(self, mock_scrape):
        mock_scrape.return_value = CrawlResult(
            markdown="# EU AI Act\n\nRegulation content.",
            title="EU AI Act Policy Page",
        )

        source = {
            "source_id": "eu_ai_act",
            "name": "EU AI Act",
            "url": "https://example.com/ai-act",
            "keywords": ["AI Act", "cybersecurity"],
            "category": "AI Regulation",
            "frequency": "daily",
        }

        result = crawl(source)

        mock_scrape.assert_called_once_with(source["url"])
        self.assertEqual(result["source_id"], "eu_ai_act")
        self.assertEqual(result["url"], source["url"])
        self.assertEqual(result["title"], "EU AI Act Policy Page")
        self.assertEqual(result["markdown"], "# EU AI Act\n\nRegulation content.")
        self.assertIn("T", result["timestamp"])

    @patch("app.crawler.service._scrape")
    def test_crawl_uses_source_name_when_title_missing(self, mock_scrape):
        mock_scrape.return_value = CrawlResult(
            markdown="Content without metadata title.",
            title="",
        )

        source = {
            "source_id": "eu_red",
            "name": "EU RED/EMC",
            "url": "https://example.com/red-emc",
            "keywords": ["RED", "EMC"],
            "category": "Product Compliance",
            "frequency": "weekly",
        }

        result = crawl(source)

        self.assertEqual(result["title"], "EU RED/EMC")


if __name__ == "__main__":
    unittest.main()
