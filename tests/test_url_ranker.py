import unittest

from app.crawler.url_ranker import rank_urls


class TestUrlRanker(unittest.TestCase):

    def _monitor(self, **overrides) -> dict:
        monitor = {
            "id": "eu_ai_act",
            "name": "EU AI Act",
            "url": "https://example.com/",
            "keywords": ["AI Act", "cybersecurity"],
            "category": "AI Regulation",
        }
        monitor.update(overrides)
        return monitor

    def test_keyword_match_in_url(self):
        monitor = self._monitor()
        links = [
            {
                "url": "https://example.com/policies/ai-act",
                "title": "Policy Page",
                "depth": 1,
            }
        ]

        ranked = rank_urls(links, monitor)

        self.assertGreater(ranked[0]["score"], 0)
        self.assertTrue(
            any("matched in URL (+30)" in reason for reason in ranked[0]["reasons"])
        )

    def test_keyword_match_in_title(self):
        monitor = self._monitor()
        links = [
            {
                "url": "https://example.com/policies/page",
                "title": "Cybersecurity Requirements",
                "depth": 1,
            }
        ]

        ranked = rank_urls(links, monitor)

        self.assertTrue(
            any("matched in title (+40)" in reason for reason in ranked[0]["reasons"])
        )

    def test_negative_term_filtering(self):
        monitor = self._monitor()
        links = [
            {
                "url": "https://example.com/privacy-policy",
                "title": "Privacy Policy",
                "depth": 1,
            }
        ]

        ranked = rank_urls(links, monitor)

        self.assertLess(ranked[0]["score"], 0)
        self.assertIn("Negative term detected (-80)", ranked[0]["reasons"])

    def test_sorts_by_score_descending(self):
        monitor = self._monitor()
        links = [
            {
                "url": "https://example.com/general",
                "title": "General Info",
                "depth": 1,
            },
            {
                "url": "https://example.com/policies/ai-act",
                "title": "AI Act Policy",
                "depth": 1,
            },
        ]

        ranked = rank_urls(links, monitor)

        self.assertGreater(ranked[0]["score"], ranked[1]["score"])
        self.assertIn("ai-act", ranked[0]["url"])

    def test_empty_keywords_still_ranks_with_depth_and_category(self):
        monitor = self._monitor(keywords=[])
        links = [
            {
                "url": "https://example.com/regulation/ai",
                "title": "AI Regulation Overview",
                "depth": 0,
            }
        ]

        ranked = rank_urls(links, monitor)

        self.assertGreaterEqual(ranked[0]["score"], 30)
        self.assertIn("Main page depth (+10)", ranked[0]["reasons"])
        self.assertTrue(
            any("Category term" in reason for reason in ranked[0]["reasons"])
        )

    def test_depth_two_or_more_applies_penalty(self):
        monitor = self._monitor()
        links = [
            {
                "url": "https://example.com/policies/ai-act/details",
                "title": "AI Act Details",
                "depth": 2,
            }
        ]

        ranked = rank_urls(links, monitor)

        self.assertIn("Deep page depth (-10)", ranked[0]["reasons"])

    def test_output_includes_score_and_reasons(self):
        monitor = self._monitor()
        links = [
            {
                "url": "https://example.com/policies/ai-act",
                "title": "AI Act Policy",
                "depth": 1,
            }
        ]

        ranked = rank_urls(links, monitor)

        self.assertIn("score", ranked[0])
        self.assertIn("reasons", ranked[0])
        self.assertIn("url", ranked[0])
        self.assertIn("title", ranked[0])
        self.assertIn("depth", ranked[0])


if __name__ == "__main__":
    unittest.main()
