import json
import unittest
from unittest.mock import MagicMock

from app.report.ai_generator import (
    DEFAULT_AI_REPORT_CONTENT,
    REPORT_TITLE,
    generate_weekly_report,
)


class TestReportAiGenerator(unittest.TestCase):

    def _report_data(self) -> dict:
        return {
            "period": {
                "start": "2026-07-01",
                "end": "2026-07-07",
            },
            "summary": {
                "total_changes": 1,
                "high_risk": 1,
                "medium_risk": 0,
                "low_risk": 0,
                "affected_modules": ["Network", "AI Features"],
            },
            "changes": [
                {
                    "title": "EU AI Act Update",
                    "category": "AI Regulation",
                    "impact_level": "HIGH",
                    "confidence": "HIGH",
                    "modules": ["Network", "AI Features"],
                    "actions": ["Review OTA security controls"],
                    "source_url": "https://example.com/ai-act",
                    "knowledge_id": 1,
                }
            ],
        }

    def test_generate_weekly_report_normal_ai_response(self):
        mock_client = MagicMock()
        mock_client.responses.create.return_value = MagicMock(
            output_text=json.dumps(
                {
                    "executive_summary": (
                        "One high-risk Smart TV regulation change requires review."
                    ),
                    "key_changes": [
                        {
                            "title": "EU AI Act Update",
                            "summary": (
                                "New obligations affect connected TV AI features."
                            ),
                            "impact_level": "High",
                            "affected_modules": ["Network", "AI Features"],
                            "recommended_actions": [
                                "Review OTA security controls"
                            ],
                        }
                    ],
                    "risk_summary": (
                        "HIGH risk changes affect network and AI modules."
                    ),
                }
            )
        )

        result = generate_weekly_report(
            self._report_data(),
            client=mock_client,
        )

        self.assertEqual(result["title"], REPORT_TITLE)
        self.assertIn("high-risk", result["executive_summary"].lower())
        self.assertEqual(len(result["key_changes"]), 1)
        self.assertEqual(result["key_changes"][0]["impact_level"], "HIGH")
        self.assertEqual(
            result["key_changes"][0]["affected_modules"],
            ["Network", "AI Features"],
        )
        self.assertTrue(result["generated_at"])

        prompt = mock_client.responses.create.call_args.kwargs["input"]
        self.assertIn("Report summary:", prompt)
        self.assertIn("EU AI Act Update", prompt)
        self.assertIn("Smart TV", prompt)
        self.assertNotIn("ADDED CONTENT", prompt)

    def test_generate_weekly_report_invalid_json_fallback(self):
        mock_client = MagicMock()
        mock_client.responses.create.return_value = MagicMock(
            output_text="not valid json"
        )

        result = generate_weekly_report(
            self._report_data(),
            client=mock_client,
        )

        self.assertEqual(result["title"], REPORT_TITLE)
        self.assertEqual(
            result["executive_summary"],
            DEFAULT_AI_REPORT_CONTENT["executive_summary"],
        )
        self.assertEqual(result["key_changes"], [])
        self.assertEqual(
            result["risk_summary"],
            DEFAULT_AI_REPORT_CONTENT["risk_summary"],
        )
        self.assertTrue(result["generated_at"])

    def test_generate_weekly_report_empty_report(self):
        mock_client = MagicMock()

        result = generate_weekly_report(
            {
                "period": {"start": "2026-07-01", "end": "2026-07-07"},
                "summary": {
                    "total_changes": 0,
                    "high_risk": 0,
                    "medium_risk": 0,
                    "low_risk": 0,
                    "affected_modules": [],
                },
                "changes": [],
            },
            client=mock_client,
        )

        self.assertEqual(result["title"], REPORT_TITLE)
        self.assertEqual(result["executive_summary"], "")
        self.assertEqual(result["key_changes"], [])
        self.assertEqual(result["risk_summary"], "")
        mock_client.responses.create.assert_not_called()

    def test_generate_weekly_report_normalizes_impact_levels(self):
        mock_client = MagicMock()
        mock_client.responses.create.return_value = MagicMock(
            output_text=json.dumps(
                {
                    "executive_summary": "Summary",
                    "key_changes": [
                        {
                            "title": "Medium Risk Act",
                            "summary": "Summary",
                            "impact_level": "medium",
                            "affected_modules": ["Network"],
                            "recommended_actions": ["Review controls"],
                        },
                        {
                            "title": "Invalid Risk Act",
                            "summary": "Summary",
                            "impact_level": "critical",
                            "affected_modules": [],
                            "recommended_actions": [],
                        },
                    ],
                    "risk_summary": "Risk summary",
                }
            )
        )

        result = generate_weekly_report(
            self._report_data(),
            client=mock_client,
        )

        impact_levels = [
            change["impact_level"] for change in result["key_changes"]
        ]
        self.assertEqual(impact_levels, ["MEDIUM", "NONE"])

    def test_generate_weekly_report_missing_fields_use_safe_defaults(self):
        mock_client = MagicMock()
        mock_client.responses.create.return_value = MagicMock(
            output_text=json.dumps({})
        )

        result = generate_weekly_report(
            self._report_data(),
            client=mock_client,
        )

        self.assertEqual(result["executive_summary"], "")
        self.assertEqual(result["key_changes"], [])
        self.assertEqual(result["risk_summary"], "")


if __name__ == "__main__":
    unittest.main()
