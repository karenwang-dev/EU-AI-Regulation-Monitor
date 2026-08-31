import unittest

from app.crawler.url_validation import (
    MonitorUrlValidationError,
    normalize_monitor_url,
    validate_monitor_url,
)


class TestUrlValidation(unittest.TestCase):

    def test_normalize_markdown_link(self):
        self.assertEqual(
            normalize_monitor_url(
                "[https://example.com/](https://example.com/)"
            ),
            "https://example.com/",
        )

    def test_validate_plain_https_url(self):
        self.assertEqual(
            validate_monitor_url("https://example.com/page"),
            "https://example.com/page",
        )

    def test_reject_non_http_url(self):
        with self.assertRaises(MonitorUrlValidationError):
            validate_monitor_url("ftp://example.com/page")

    def test_reject_empty_url(self):
        with self.assertRaises(MonitorUrlValidationError):
            validate_monitor_url("")


if __name__ == "__main__":
    unittest.main()
