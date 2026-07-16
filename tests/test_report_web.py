import gc
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.report.storage import get_report, save_report
from app.storage.service import StorageService
from app.web.app import create_dashboard_app


class TestReportWeb(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        base_path = Path(self.temp_dir.name)
        self.reports_dir = base_path / "reports"
        self.store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )
        self.client = TestClient(
            create_dashboard_app(
                storage_service=self.store,
                reports_dir=self.reports_dir,
            )
        )

    def tearDown(self):
        self.client = None
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    def _sample_report(self) -> dict:
        return {
            "title": "Weekly Regulation Monitoring Report",
            "generated_at": "2026-07-16T12:00:00",
            "period": {
                "start": "2026-07-09",
                "end": "2026-07-16",
            },
            "summary": {
                "total_changes": 1,
                "high_risk": 1,
                "medium_risk": 0,
                "low_risk": 0,
                "affected_modules": ["Network", "AI Features"],
            },
            "executive_summary": (
                "One high-risk Smart TV regulation change requires review."
            ),
            "key_changes": [
                {
                    "title": "EU AI Act Update",
                    "summary": "New obligations affect connected TV AI features.",
                    "impact_level": "HIGH",
                    "affected_modules": ["Network", "AI Features"],
                    "recommended_actions": ["Review OTA security controls"],
                    "source_url": "https://example.com/ai-act",
                    "knowledge_id": 1,
                }
            ],
            "risk_summary": "HIGH risk changes affect network and AI modules.",
        }

    def test_reports_page_empty_state(self):
        response = self.client.get("/reports")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Weekly Reports", content)
        self.assertIn(b"Generate Latest Report", content)
        self.assertIn(b"No executive summary available.", content)
        self.assertIn(b"No key changes available.", content)
        self.assertIn(b"No risk summary available.", content)
        self.assertIn(b"Total Changes", content)
        self.assertIn(b">0<", content)

    def test_reports_page_renders_saved_report(self):
        save_report(self._sample_report(), reports_dir=self.reports_dir)

        response = self.client.get("/reports")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"EU AI Act Update", content)
        self.assertIn(b"One high-risk Smart TV regulation change requires review.", content)
        self.assertIn(b"Review OTA security controls", content)
        self.assertIn(b"https://example.com/ai-act", content)
        self.assertIn(b"HIGH risk changes affect network and AI modules.", content)
        self.assertIn(b"Network", content)
        self.assertIn(b"AI Features", content)

    def test_latest_report_api(self):
        saved = save_report(self._sample_report(), reports_dir=self.reports_dir)

        response = self.client.get("/api/reports/latest")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], saved["id"])
        self.assertEqual(data["title"], "Weekly Regulation Monitoring Report")
        self.assertEqual(data["summary"]["high_risk"], 1)
        self.assertEqual(len(data["key_changes"]), 1)

    def test_latest_report_api_empty_returns_404(self):
        response = self.client.get("/api/reports/latest")

        self.assertEqual(response.status_code, 404)

    def test_report_history_and_detail_api(self):
        saved = save_report(self._sample_report(), reports_dir=self.reports_dir)

        history_response = self.client.get("/api/reports")
        self.assertEqual(history_response.status_code, 200)
        history = history_response.json()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["id"], saved["id"])

        detail_response = self.client.get(f"/api/reports/{saved['id']}")
        self.assertEqual(detail_response.status_code, 200)
        detail = detail_response.json()
        self.assertEqual(detail["executive_summary"], self._sample_report()["executive_summary"])

    def test_report_generation_api(self):
        report_data = {
            "period": {"start": "2026-07-09", "end": "2026-07-16"},
            "summary": {
                "total_changes": 1,
                "high_risk": 1,
                "medium_risk": 0,
                "low_risk": 0,
                "affected_modules": ["Network"],
            },
            "changes": [
                {
                    "title": "Generated Regulation",
                    "category": "AI Regulation",
                    "impact_level": "HIGH",
                    "confidence": "HIGH",
                    "modules": ["Network"],
                    "actions": ["Review controls"],
                    "source_url": "https://example.com/generated",
                    "knowledge_id": 3,
                }
            ],
        }
        generated = {
            "title": "Weekly Regulation Monitoring Report",
            "executive_summary": "Generated summary.",
            "key_changes": [
                {
                    "title": "Generated Regulation",
                    "summary": "Generated change summary.",
                    "impact_level": "HIGH",
                    "affected_modules": ["Network"],
                    "recommended_actions": ["Review controls"],
                }
            ],
            "risk_summary": "Generated risk summary.",
            "generated_at": "2026-07-16T15:00:00",
        }

        client = TestClient(
            create_dashboard_app(
                storage_service=self.store,
                reports_dir=self.reports_dir,
                build_weekly_report_fn=lambda **kwargs: report_data,
                generate_weekly_report_fn=lambda data, client=None: generated,
            )
        )

        response = client.post("/api/reports/generate")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["executive_summary"], "Generated summary.")
        self.assertEqual(data["key_changes"][0]["source_url"], "https://example.com/generated")
        self.assertTrue(get_report(data["id"], reports_dir=self.reports_dir))

        saved_path = self.reports_dir / data["filename"]
        self.assertTrue(saved_path.exists())
        payload = json.loads(saved_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["risk_summary"], "Generated risk summary.")

    def test_navigation_contains_reports(self):
        response = self.client.get("/reports")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b'href="/reports"', content)
        self.assertIn(b"Reports", content)
        self.assertIn(b"nav-link active", content)


if __name__ == "__main__":
    unittest.main()
