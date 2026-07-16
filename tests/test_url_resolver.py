import unittest
from unittest.mock import MagicMock

from app.crawler.url_resolver import resolve_monitor_urls


class TestUrlResolver(unittest.TestCase):

    def _monitor(self, **overrides) -> dict:
        monitor = {
            "id": "eu_ai_act",
            "name": "EU AI Act",
            "url": "https://example.com/",
            "keywords": ["AI Act", "cybersecurity"],
            "category": "AI Regulation",
            "frequency": "daily",
            "enabled": True,
            "crawl_mode": "single",
            "max_depth": 0,
            "max_pages": 1,
        }
        monitor.update(overrides)
        return monitor

    def test_single_mode_returns_only_monitor_url(self):
        monitor = self._monitor(crawl_mode="single")
        discover_mock = MagicMock()

        results = resolve_monitor_urls(monitor, discover_links_fn=discover_mock)

        discover_mock.assert_not_called()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], monitor["url"])
        self.assertEqual(results[0]["depth"], 0)

    def test_smart_mode_includes_root_and_discovered_urls(self):
        monitor = self._monitor(
            crawl_mode="smart",
            max_depth=2,
            max_pages=10,
        )
        discover_mock = MagicMock(
            return_value=[
                {
                    "url": "https://example.com/policies/ai-act",
                    "title": "AI Act Policy",
                    "depth": 1,
                },
                {
                    "url": "https://example.com/policies/cybersecurity",
                    "title": "Cybersecurity Policy",
                    "depth": 2,
                },
            ]
        )

        results = resolve_monitor_urls(monitor, discover_links_fn=discover_mock)

        discover_mock.assert_called_once_with(
            monitor["url"],
            monitor["keywords"],
            max_depth=2,
            max_pages=10,
        )
        self.assertEqual(len(results), 3)
        urls = {item["url"] for item in results}
        self.assertIn(monitor["url"], urls)
        self.assertIn("https://example.com/policies/ai-act", urls)
        self.assertIn("https://example.com/policies/cybersecurity", urls)
        self.assertTrue(all("score" in item for item in results))
        self.assertGreater(results[0]["score"], results[-1]["score"])

    def test_smart_mode_respects_max_pages(self):
        monitor = self._monitor(
            crawl_mode="smart",
            max_depth=2,
            max_pages=2,
        )
        discover_mock = MagicMock(
            return_value=[
                {
                    "url": "https://example.com/one",
                    "title": "One",
                    "depth": 1,
                },
                {
                    "url": "https://example.com/policies/ai-act",
                    "title": "AI Act Policy",
                    "depth": 1,
                },
                {
                    "url": "https://example.com/three",
                    "title": "Three",
                    "depth": 1,
                },
            ]
        )

        results = resolve_monitor_urls(monitor, discover_links_fn=discover_mock)

        self.assertEqual(len(results), 2)
        urls = [item["url"] for item in results]
        self.assertIn("https://example.com/policies/ai-act", urls)
        self.assertEqual(results[0]["score"], max(item["score"] for item in results))

    def test_smart_mode_deduplicates_urls(self):
        monitor = self._monitor(
            crawl_mode="smart",
            max_depth=1,
            max_pages=5,
        )
        discover_mock = MagicMock(
            return_value=[
                {
                    "url": "https://example.com/",
                    "title": "Duplicate Root",
                    "depth": 1,
                },
                {
                    "url": "https://example.com/policies/ai-act",
                    "title": "AI Act",
                    "depth": 1,
                },
            ]
        )

        results = resolve_monitor_urls(monitor, discover_links_fn=discover_mock)

        urls = [item["url"] for item in results]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertEqual(len(results), 2)

    def test_smart_mode_uses_ranking_before_limiting_pages(self):
        monitor = self._monitor(
            crawl_mode="smart",
            max_depth=1,
            max_pages=2,
        )
        discover_mock = MagicMock(
            return_value=[
                {
                    "url": "https://example.com/contact",
                    "title": "Contact Us",
                    "depth": 1,
                },
                {
                    "url": "https://example.com/policies/ai-act",
                    "title": "AI Act Policy",
                    "depth": 1,
                },
            ]
        )
        rank_mock = MagicMock(
            side_effect=lambda links, _monitor: sorted(
                [
                    {
                        **link,
                        "score": 100 if "ai-act" in link["url"] else -50,
                        "reasons": ["test"],
                    }
                    for link in links
                ],
                key=lambda item: item["score"],
                reverse=True,
            )
        )

        results = resolve_monitor_urls(
            monitor,
            discover_links_fn=discover_mock,
            rank_urls_fn=rank_mock,
        )

        rank_mock.assert_called_once()
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["url"], "https://example.com/policies/ai-act")


if __name__ == "__main__":
    unittest.main()
