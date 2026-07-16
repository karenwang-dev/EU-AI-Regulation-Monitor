import json
import unittest
from unittest.mock import MagicMock, patch

from app.ai.regulation_extractor import (
    DEFAULT_EXTRACTION_RESULT,
    EXTRACTION_MODE_DIFF,
    EXTRACTION_MODE_FULL,
    extract_regulation,
)


class TestRegulationExtractor(unittest.TestCase):

    def _monitor(self) -> dict:
        return {
            "id": "eu_ai_act",
            "name": "EU AI Act",
            "url": "https://example.com/ai-act",
            "keywords": ["AI Act", "cybersecurity", "Smart TV"],
            "category": "AI Regulation",
            "frequency": "daily",
            "enabled": True,
        }

    def _sample_content(self) -> str:
        return (
            "# EU AI Act update\n\n"
            "New obligations for high-risk AI systems embedded in "
            "consumer electronics take effect on 2 August 2028."
        )

    def _diff_result(self) -> dict:
        return {
            "source_id": "eu_ai_act",
            "old_snapshot_id": 1,
            "new_snapshot_id": 2,
            "changed": True,
            "added_content": [
                "Extended transition period until 2 August 2028"
            ],
            "removed_content": [
                "Previous transition period until 2 August 2027"
            ],
            "diff_text": (
                "-Previous transition period until 2 August 2027\n"
                "+Extended transition period until 2 August 2028"
            ),
        }

    def _valid_extraction_payload(self, **overrides) -> dict:
        payload = {
            "title": "EU AI Act Implementation Update",
            "publish_date": "2026-05-07",
            "summary": "Extended transition period for embedded AI.",
            "category": "AI Regulation",
            "regulation_type": "amendment",
            "effective_date": "2028-08-02",
            "affected_countries": ["EU", " Germany "],
            "affected_products": ["Smart TV", ""],
            "affected_modules": ["AI Features", "Network"],
            "key_requirements": [
                "Assess embedded high-risk AI systems"
            ],
            "actions_required": ["Review product compliance plan"],
            "is_regulation_content": True,
            "confidence": "high",
        }
        payload.update(overrides)
        return payload

    @patch("app.ai.regulation_extractor.client.responses.create")
    def test_extract_regulation_returns_normalized_json(
        self,
        mock_create,
    ):
        mock_create.return_value = MagicMock(
            output_text=json.dumps(self._valid_extraction_payload())
        )

        result = extract_regulation(
            self._sample_content(),
            self._monitor(),
        )

        self.assertEqual(result["title"], "EU AI Act Implementation Update")
        self.assertEqual(result["regulation_type"], "AMENDMENT")
        self.assertEqual(result["confidence"], "HIGH")
        self.assertTrue(result["is_regulation_content"])
        self.assertEqual(result["affected_countries"], ["EU", "Germany"])
        self.assertEqual(result["affected_products"], ["Smart TV"])
        mock_create.assert_called_once()

        prompt = mock_create.call_args.kwargs["input"]
        self.assertIn("FULL webpage content", prompt)
        self.assertIn("EU AI Act", prompt)
        self.assertIn("AI Act", prompt)
        self.assertIn("high-risk AI systems", prompt)
        self.assertNotIn("ADDED CONTENT", prompt)

    @patch("app.ai.regulation_extractor.client.responses.create")
    def test_extract_regulation_handles_invalid_json(
        self,
        mock_create,
    ):
        mock_create.return_value = MagicMock(
            output_text="not valid json"
        )

        result = extract_regulation(
            self._sample_content(),
            self._monitor(),
        )

        self.assertEqual(result, DEFAULT_EXTRACTION_RESULT)

    @patch("app.ai.regulation_extractor.client.responses.create")
    def test_extract_regulation_works_without_monitor(
        self,
        mock_create,
    ):
        mock_create.return_value = MagicMock(
            output_text=json.dumps(
                {
                    "title": "Generic regulation page",
                    "publish_date": "",
                    "summary": "Summary text",
                    "category": "",
                    "regulation_type": "OTHER",
                    "effective_date": "",
                    "affected_countries": [],
                    "affected_products": [],
                    "affected_modules": [],
                    "key_requirements": [],
                    "actions_required": [],
                    "is_regulation_content": False,
                    "confidence": "LOW",
                }
            )
        )

        result = extract_regulation(self._sample_content())

        self.assertEqual(result["title"], "Generic regulation page")
        self.assertFalse(result["is_regulation_content"])

        prompt = mock_create.call_args.kwargs["input"]
        self.assertIn("high-risk AI systems", prompt)
        self.assertIn("Monitor metadata:", prompt)

    @patch("app.ai.regulation_extractor.client.responses.create")
    def test_extract_regulation_normalizes_unknown_regulation_type(
        self,
        mock_create,
    ):
        mock_create.return_value = MagicMock(
            output_text=json.dumps(
                {
                    "title": "Press release",
                    "publish_date": "",
                    "summary": "",
                    "category": "",
                    "regulation_type": "press-release",
                    "effective_date": "",
                    "affected_countries": [],
                    "affected_products": [],
                    "affected_modules": [],
                    "key_requirements": [],
                    "actions_required": [],
                    "is_regulation_content": False,
                    "confidence": "unknown",
                }
            )
        )

        result = extract_regulation(
            self._sample_content(),
            self._monitor(),
        )

        self.assertEqual(result["regulation_type"], "OTHER")
        self.assertEqual(result["confidence"], "LOW")

    @patch("app.ai.regulation_extractor.client.responses.create")
    def test_extract_regulation_full_mode_is_default(
        self,
        mock_create,
    ):
        mock_create.return_value = MagicMock(
            output_text=json.dumps(self._valid_extraction_payload())
        )

        extract_regulation(
            self._sample_content(),
            self._monitor(),
            mode=EXTRACTION_MODE_FULL,
        )

        prompt = mock_create.call_args.kwargs["input"]
        self.assertIn("FULL webpage content", prompt)
        self.assertNotIn("ADDED CONTENT", prompt)

    @patch("app.ai.regulation_extractor.client.responses.create")
    def test_extract_regulation_diff_mode_uses_diff_prompt(
        self,
        mock_create,
    ):
        mock_create.return_value = MagicMock(
            output_text=json.dumps(
                self._valid_extraction_payload(
                    title="AI Act transition update",
                    summary="Transition period extended to 2028.",
                )
            )
        )

        result = extract_regulation(
            monitor=self._monitor(),
            mode=EXTRACTION_MODE_DIFF,
            diff_result=self._diff_result(),
        )

        self.assertEqual(result["title"], "AI Act transition update")
        self.assertEqual(result["regulation_type"], "AMENDMENT")
        mock_create.assert_called_once()

        prompt = mock_create.call_args.kwargs["input"]
        self.assertIn("changed content below", prompt)
        self.assertIn("ADDED CONTENT", prompt)
        self.assertIn("REMOVED CONTENT", prompt)
        self.assertIn("Extended transition period until 2 August 2028", prompt)
        self.assertIn(
            "Previous transition period until 2 August 2027",
            prompt,
        )
        self.assertNotIn("FULL webpage content", prompt)

    @patch("app.ai.regulation_extractor.client.responses.create")
    def test_extract_regulation_diff_mode_ignores_full_content(
        self,
        mock_create,
    ):
        mock_create.return_value = MagicMock(
            output_text=json.dumps(self._valid_extraction_payload())
        )

        extract_regulation(
            content="This full-page content should not appear in diff mode.",
            monitor=self._monitor(),
            mode=EXTRACTION_MODE_DIFF,
            diff_result=self._diff_result(),
        )

        prompt = mock_create.call_args.kwargs["input"]
        self.assertNotIn(
            "This full-page content should not appear in diff mode.",
            prompt,
        )

    def test_extract_regulation_diff_mode_requires_diff_result(self):
        with self.assertRaises(ValueError):
            extract_regulation(
                monitor=self._monitor(),
                mode=EXTRACTION_MODE_DIFF,
            )

    def test_extract_regulation_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            extract_regulation(
                self._sample_content(),
                self._monitor(),
                mode="snapshot",
            )


if __name__ == "__main__":
    unittest.main()
