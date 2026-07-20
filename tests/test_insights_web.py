import gc
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.storage.service import StorageService
from app.web.app import create_dashboard_app
from app.web.insight_helper import (
    build_compliance_insight,
    build_insight_summary,
    filter_compliance_insights,
)


class TestInsightHelper(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        base_path = Path(self.temp_dir.name)
        self.store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )

    def tearDown(self):
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    def test_build_compliance_insight_uses_analysis_fields(self):
        snapshot = self.store.save_snapshot(
            {
                "source_id": "eu_ai_act",
                "url": "https://example.com/ai-act",
                "title": "EU AI Act",
                "markdown": "# EU AI Act",
                "timestamp": "2026-07-15T12:00:00",
            }
        )
        self.store.save_analysis(
            snapshot["id"],
            {
                "impact_level": "HIGH",
                "affected_modules": ["Network"],
                "recommended_actions": ["Review OTA security controls"],
                "regulation_extraction": {
                    "publish_date": "2026-05-07",
                    "effective_date": "2028-08-02",
                },
            },
        )
        knowledge = {
            "id": 1,
            "snapshot_id": snapshot["id"],
            "title": "EU AI Act Update",
            "category": "AI Regulation",
            "effective_date": "",
            "modules": [],
            "actions": [],
            "summary": "Cybersecurity obligations.",
        }

        insight = build_compliance_insight(knowledge, self.store)

        self.assertEqual(insight["impact_level"], "HIGH")
        self.assertEqual(insight["affected_modules"], ["Network"])
        self.assertEqual(
            insight["recommended_actions"],
            ["Review OTA security controls"],
        )
        self.assertEqual(insight["publish_date"], "2026-05-07")
        self.assertEqual(insight["effective_date"], "2028-08-02")

    def test_build_compliance_insight_missing_fields_use_na(self):
        insight = build_compliance_insight({"id": 1}, self.store)

        self.assertEqual(insight["title"], "N/A")
        self.assertEqual(insight["category"], "N/A")
        self.assertEqual(insight["impact_level"], "NONE")
        self.assertEqual(insight["publish_date"], "N/A")
        self.assertEqual(insight["effective_date"], "N/A")

    def test_filter_and_summary(self):
        insights = [
            {
                "title": "High Risk Act",
                "category": "AI Regulation",
                "impact_level": "HIGH",
                "affected_modules": ["Network"],
                "recommended_actions": ["Review controls"],
                "summary": "High risk summary",
            },
            {
                "title": "Low Risk Act",
                "category": "Product Compliance",
                "impact_level": "LOW",
                "affected_modules": ["Display"],
                "recommended_actions": ["Update docs"],
                "summary": "Low risk summary",
            },
        ]

        filtered = filter_compliance_insights(
            insights,
            query="network",
            impact="HIGH",
        )
        summary = build_insight_summary(filtered)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["title"], "High Risk Act")
        self.assertEqual(summary["high_priority"], 1)
        self.assertEqual(summary["total_regulations"], 1)


class TestInsightsWeb(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        base_path = Path(self.temp_dir.name)
        self.store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )
        self.client = TestClient(
            create_dashboard_app(storage_service=self.store)
        )

    def tearDown(self):
        self.client = None
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    def _seed_high_insight(self):
        snapshot = self.store.save_snapshot(
            {
                "source_id": "eu_ai_act",
                "url": "https://example.com/ai-act",
                "title": "EU AI Act",
                "markdown": "# EU AI Act",
                "timestamp": "2026-07-15T12:00:00",
            }
        )
        self.store.save_analysis(
            snapshot["id"],
            {
                "impact_level": "HIGH",
                "affected_modules": ["Network", "AI Features"],
                "recommended_actions": ["Review OTA security controls"],
                "regulation_extraction": {
                    "publish_date": "2026-05-07",
                    "effective_date": "2028-08-02",
                },
            },
        )
        saved = self.store.save_knowledge_item(
            {
                "snapshot_id": snapshot["id"],
                "source_id": "eu_ai_act",
                "title": "EU AI Act Cybersecurity Update",
                "category": "AI Regulation",
                "regulation_type": "AMENDMENT",
                "summary": "Cybersecurity obligations for connected devices.",
                "effective_date": "2028-08-02",
                "countries": ["EU"],
                "products": ["Smart TV"],
                "modules": ["Network", "AI Features"],
                "requirements": ["Assess cybersecurity controls"],
                "actions": ["Update compliance checklist"],
                "confidence": "HIGH",
            }
        )
        return saved

    def test_insights_page_renders_on_knowledge(self):
        saved = self._seed_high_insight()

        response = self.client.get("/knowledge")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Knowledge Base", content)
        self.assertIn(b"EU AI Act Cybersecurity Update", content)
        self.assertIn(b"AI Regulation", content)
        self.assertIn(b"Update compliance checklist", content)
        self.assertIn(b"2028-08-02", content)
        self.assertIn(f'href="/knowledge/{saved["id"]}"'.encode(), content)
        self.assertIn(b"Recommended Actions", content)
        self.assertIn(b"Effective Date", content)

    def test_insights_summary_cards(self):
        self._seed_high_insight()

        response = self.client.get("/knowledge")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"High Priority", content)
        self.assertIn(b"Medium Priority", content)
        self.assertIn(b"Low Priority", content)
        self.assertIn(b"Total Regulations", content)

    def test_insights_impact_filter(self):
        self._seed_high_insight()
        snapshot = self.store.save_snapshot(
            {
                "source_id": "eu_red",
                "url": "https://example.com/red",
                "title": "RED Directive",
                "markdown": "# RED",
                "timestamp": "2026-07-16T12:00:00",
            }
        )
        self.store.save_analysis(
            snapshot["id"],
            {"impact_level": "LOW"},
        )
        self.store.save_knowledge_item(
            {
                "snapshot_id": snapshot["id"],
                "source_id": "eu_red",
                "title": "RED Directive Update",
                "category": "Product Compliance",
                "regulation_type": "NEW",
                "summary": "Radio equipment requirements.",
                "effective_date": "2027-01-01",
                "countries": ["EU"],
                "products": ["Smart TV"],
                "modules": ["Radio equipment"],
                "requirements": ["Review RED documentation"],
                "actions": ["Schedule compliance review"],
                "confidence": "MEDIUM",
            }
        )

        response = self.client.get("/knowledge?impact=HIGH")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"EU AI Act Cybersecurity Update", content)
        self.assertNotIn(b"RED Directive Update", content)

    def test_insights_category_and_module_filters(self):
        self._seed_high_insight()
        snapshot = self.store.save_snapshot(
            {
                "source_id": "eu_red",
                "url": "https://example.com/red",
                "title": "RED Directive",
                "markdown": "# RED",
                "timestamp": "2026-07-16T12:00:00",
            }
        )
        self.store.save_analysis(snapshot["id"], {"impact_level": "LOW"})
        self.store.save_knowledge_item(
            {
                "snapshot_id": snapshot["id"],
                "source_id": "eu_red",
                "title": "RED Directive Update",
                "category": "Product Compliance",
                "regulation_type": "NEW",
                "summary": "Radio equipment requirements.",
                "effective_date": "2027-01-01",
                "countries": ["EU"],
                "products": ["Smart TV"],
                "modules": ["Radio equipment"],
                "requirements": ["Review RED documentation"],
                "actions": ["Schedule compliance review"],
                "confidence": "MEDIUM",
            }
        )

        category_response = self.client.get(
            "/knowledge?category=Product%20Compliance"
        )
        self.assertEqual(category_response.status_code, 200)
        self.assertIn(b"RED Directive Update", category_response.content)
        self.assertNotIn(
            b"EU AI Act Cybersecurity Update",
            category_response.content,
        )

        module_response = self.client.get("/knowledge?module=Network")
        self.assertEqual(module_response.status_code, 200)
        self.assertIn(b"EU AI Act Cybersecurity Update", module_response.content)
        self.assertNotIn(b"RED Directive Update", module_response.content)

    def test_insights_keyword_search(self):
        self._seed_high_insight()

        response = self.client.get("/knowledge?q=cybersecurity")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"EU AI Act Cybersecurity Update", response.content)

    def test_insights_empty_state(self):
        response = self.client.get("/knowledge")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"No knowledge items match your filters.", content)
        self.assertIn(b"Total Regulations", content)

    def test_insights_redirects_to_knowledge(self):
        saved = self._seed_high_insight()

        response = self.client.get("/insights?impact=HIGH", follow_redirects=False)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["location"], "/knowledge?impact=HIGH")

        followed = self.client.get("/insights?impact=HIGH")
        self.assertEqual(followed.status_code, 200)
        self.assertIn(b"EU AI Act Cybersecurity Update", followed.content)
        self.assertIn(f'href="/knowledge/{saved["id"]}"'.encode(), followed.content)

    def test_navigation_no_longer_contains_insights(self):
        response = self.client.get("/knowledge")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b'href="/knowledge"', content)
        self.assertIn(b"Knowledge Base", content)
        self.assertNotIn(b'href="/insights"', content)
        self.assertNotIn(b">Insights<", content)
        self.assertIn(b"nav-link active", content)


if __name__ == "__main__":
    unittest.main()
