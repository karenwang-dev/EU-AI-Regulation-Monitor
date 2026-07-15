import json
import unittest
from unittest.mock import MagicMock, patch

from app.ai.impact_analyzer import (
    DEFAULT_IMPACT_RESULT,
    analyze_change_impact,
)


class TestImpactAnalyzer(unittest.TestCase):

    def _diff_result(self) -> dict:
        return {
            "source_id": "ec",
            "old_snapshot_id": 1,
            "new_snapshot_id": 2,
            "changed": True,
            "added_content": [
                "New cybersecurity requirements for connected TVs"
            ],
            "removed_content": [],
            "diff_text": "+New cybersecurity requirements for connected TVs",
        }

    def _monitor(self) -> dict:
        return {
            "id": "ec",
            "name": "European Commission",
            "url": "https://example.com/ec",
            "keywords": ["EU Regulation", "Smart TV", "cybersecurity"],
            "category": "EU Policy",
            "frequency": "daily",
            "enabled": True,
        }

    @patch("app.ai.impact_analyzer.client.responses.create")
    def test_analyze_change_impact_returns_normalized_json(
        self,
        mock_create,
    ):
        mock_create.return_value = MagicMock(
            output_text=json.dumps(
                {
                    "impact_level": "High",
                    "affected_modules": ["Network", "AI Features"],
                    "reason": "New cybersecurity obligations affect connected TV software.",
                    "recommended_actions": [
                        "Review OTA security controls"
                    ],
                    "confidence": "medium",
                }
            )
        )

        result = analyze_change_impact(
            self._diff_result(),
            self._monitor(),
        )

        self.assertEqual(result["impact_level"], "HIGH")
        self.assertEqual(result["affected_modules"], ["Network", "AI Features"])
        self.assertEqual(result["confidence"], "MEDIUM")
        mock_create.assert_called_once()

        prompt = mock_create.call_args.kwargs["input"]
        self.assertIn("ADDED CONTENT", prompt)
        self.assertIn("Smart TV", prompt)
        self.assertNotIn("Analyze the full webpage", prompt)

    @patch("app.ai.impact_analyzer.client.responses.create")
    def test_analyze_change_impact_handles_invalid_json(
        self,
        mock_create,
    ):
        mock_create.return_value = MagicMock(
            output_text="not valid json"
        )

        result = analyze_change_impact(
            self._diff_result(),
            self._monitor(),
        )

        self.assertEqual(result, DEFAULT_IMPACT_RESULT)


if __name__ == "__main__":
    unittest.main()
