import gc
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.report.builder import build_weekly_report
from app.storage.service import StorageService


class TestReportBuilder(unittest.TestCase):

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
        self.monitor = {
            "id": "eu_ai_act",
            "name": "EU AI Act",
            "url": "https://example.com/ai-act",
            "keywords": ["AI Act"],
            "category": "AI Regulation",
            "frequency": "daily",
            "enabled": True,
        }
        self.monitors_patcher = mock.patch(
            "app.report.builder.load_monitors",
            return_value=[self.monitor],
        )
        self.monitors_patcher.start()

    def tearDown(self):
        self.monitors_patcher.stop()
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    def _set_diff_created_at(self, diff_id: int, created_at: str) -> None:
        with self.store._connect() as connection:
            connection.execute(
                "UPDATE diffs SET created_at = ? WHERE id = ?",
                (created_at, diff_id),
            )

    def _seed_change(
        self,
        *,
        title: str = "EU AI Act Update",
        impact_level: str = "HIGH",
        modules: list[str] | None = None,
        actions: list[str] | None = None,
        created_at: str = "2026-07-10T12:00:00",
        with_knowledge: bool = True,
        source_id: str = "eu_ai_act",
    ) -> dict:
        snapshot = self.store.save_snapshot(
            {
                "source_id": source_id,
                "url": "https://example.com/ai-act",
                "title": "EU AI Act",
                "markdown": "# EU AI Act",
                "timestamp": created_at,
            }
        )
        self.store.save_analysis(
            snapshot["id"],
            {
                "impact_level": impact_level,
                "affected_modules": modules or ["Network"],
                "recommended_actions": actions or ["Review OTA security controls"],
                "confidence": "HIGH",
                "regulation_extraction": {
                    "title": title,
                    "category": "AI Regulation",
                },
                "evidence": [
                    {
                        "url": "https://example.com/ai-act",
                        "source_id": source_id,
                    }
                ],
            },
        )
        diff = self.store.save_diff(
            {
                "source_id": source_id,
                "old_snapshot_id": None,
                "new_snapshot_id": snapshot["id"],
                "changed": True,
                "added_content": ["Added section"],
                "removed_content": [],
                "diff_text": "+Added section",
            }
        )
        self._set_diff_created_at(diff["id"], created_at)

        knowledge_id = None
        if with_knowledge:
            knowledge = self.store.save_knowledge_item(
                {
                    "snapshot_id": snapshot["id"],
                    "source_id": source_id,
                    "title": title,
                    "category": "AI Regulation",
                    "regulation_type": "AMENDMENT",
                    "summary": "Cybersecurity obligations.",
                    "effective_date": "2028-08-02",
                    "countries": ["EU"],
                    "products": ["Smart TV"],
                    "modules": modules or ["Network", "AI Features"],
                    "requirements": ["Assess cybersecurity controls"],
                    "actions": actions or ["Update compliance checklist"],
                    "confidence": "HIGH",
                }
            )
            knowledge_id = knowledge["id"]

        return {
            "snapshot_id": snapshot["id"],
            "diff_id": diff["id"],
            "knowledge_id": knowledge_id,
            "title": title,
        }

    def test_empty_report(self):
        report = build_weekly_report(
            start_date="2026-07-01",
            end_date="2026-07-31",
            storage=self.store,
        )

        self.assertEqual(report["period"]["start"], "2026-07-01")
        self.assertEqual(report["period"]["end"], "2026-07-31")
        self.assertEqual(report["summary"]["total_changes"], 0)
        self.assertEqual(report["summary"]["high_risk"], 0)
        self.assertEqual(report["summary"]["medium_risk"], 0)
        self.assertEqual(report["summary"]["low_risk"], 0)
        self.assertEqual(report["summary"]["affected_modules"], [])
        self.assertEqual(report["changes"], [])

    def test_date_filtering(self):
        in_period = self._seed_change(
            title="In Period Regulation",
            created_at="2026-07-10T12:00:00",
        )
        self._seed_change(
            title="Out Of Period Regulation",
            created_at="2026-06-01T12:00:00",
        )

        report = build_weekly_report(
            start_date="2026-07-01",
            end_date="2026-07-31",
            storage=self.store,
        )

        self.assertEqual(report["summary"]["total_changes"], 1)
        self.assertEqual(report["changes"][0]["title"], "In Period Regulation")
        self.assertEqual(
            report["changes"][0]["knowledge_id"],
            in_period["knowledge_id"],
        )

    def test_high_medium_low_counting(self):
        self._seed_change(
            title="High Risk Regulation",
            impact_level="HIGH",
            created_at="2026-07-10T12:00:00",
        )
        self._seed_change(
            title="Medium Risk Regulation",
            impact_level="MEDIUM",
            created_at="2026-07-11T12:00:00",
        )
        self._seed_change(
            title="Low Risk Regulation",
            impact_level="LOW",
            created_at="2026-07-12T12:00:00",
        )
        self._seed_change(
            title="No Impact Regulation",
            impact_level="NONE",
            created_at="2026-07-13T12:00:00",
        )

        report = build_weekly_report(
            start_date="2026-07-01",
            end_date="2026-07-31",
            storage=self.store,
        )

        self.assertEqual(report["summary"]["total_changes"], 4)
        self.assertEqual(report["summary"]["high_risk"], 1)
        self.assertEqual(report["summary"]["medium_risk"], 1)
        self.assertEqual(report["summary"]["low_risk"], 1)

    def test_module_aggregation(self):
        self._seed_change(
            title="Network Regulation",
            modules=["Network"],
            created_at="2026-07-10T12:00:00",
        )
        self._seed_change(
            title="Display Regulation",
            modules=["Display", "Network"],
            created_at="2026-07-11T12:00:00",
        )

        report = build_weekly_report(
            start_date="2026-07-01",
            end_date="2026-07-31",
            storage=self.store,
        )

        self.assertEqual(
            report["summary"]["affected_modules"],
            ["Display", "Network"],
        )

    def test_duplicate_removal(self):
        self._seed_change(
            title="EU AI Act Update",
            impact_level="LOW",
            created_at="2026-07-10T12:00:00",
        )
        self._seed_change(
            title="EU AI Act Update",
            impact_level="HIGH",
            created_at="2026-07-11T12:00:00",
        )

        report = build_weekly_report(
            start_date="2026-07-01",
            end_date="2026-07-31",
            storage=self.store,
        )

        self.assertEqual(report["summary"]["total_changes"], 1)
        self.assertEqual(report["changes"][0]["impact_level"], "HIGH")

    def test_sorting(self):
        self._seed_change(
            title="Low First",
            impact_level="LOW",
            created_at="2026-07-10T12:00:00",
        )
        self._seed_change(
            title="High First",
            impact_level="HIGH",
            created_at="2026-07-11T12:00:00",
        )
        self._seed_change(
            title="Medium Middle",
            impact_level="MEDIUM",
            created_at="2026-07-12T12:00:00",
        )

        report = build_weekly_report(
            start_date="2026-07-01",
            end_date="2026-07-31",
            storage=self.store,
        )

        impact_levels = [
            change["impact_level"] for change in report["changes"]
        ]
        self.assertEqual(impact_levels, ["HIGH", "MEDIUM", "LOW"])

    def test_missing_fields_use_safe_defaults(self):
        snapshot = self.store.save_snapshot(
            {
                "source_id": "eu_ai_act",
                "url": "https://example.com/ai-act",
                "title": "EU AI Act",
                "markdown": "# EU AI Act",
                "timestamp": "2026-07-10T12:00:00",
            }
        )
        diff = self.store.save_diff(
            {
                "source_id": "eu_ai_act",
                "old_snapshot_id": None,
                "new_snapshot_id": snapshot["id"],
                "changed": True,
                "added_content": ["Added section"],
                "removed_content": [],
                "diff_text": "+Added section",
            }
        )
        self._set_diff_created_at(diff["id"], "2026-07-10T12:00:00")

        report = build_weekly_report(
            start_date="2026-07-01",
            end_date="2026-07-31",
            storage=self.store,
        )

        self.assertEqual(report["summary"]["total_changes"], 1)
        change = report["changes"][0]
        self.assertEqual(change["title"], "EU AI Act")
        self.assertEqual(change["category"], "AI Regulation")
        self.assertEqual(change["impact_level"], "NONE")
        self.assertEqual(change["confidence"], "")
        self.assertEqual(change["modules"], [])
        self.assertEqual(change["actions"], [])
        self.assertEqual(change["source_url"], "https://example.com/ai-act")
        self.assertIsNone(change["knowledge_id"])

    def test_change_entry_includes_compliance_insight_fields(self):
        seeded = self._seed_change(
            title="Insight Backed Regulation",
            modules=["Network", "AI Features"],
            actions=["Update compliance checklist"],
            created_at="2026-07-10T12:00:00",
        )

        report = build_weekly_report(
            start_date="2026-07-01",
            end_date="2026-07-31",
            storage=self.store,
        )

        change = report["changes"][0]
        self.assertEqual(change["title"], "Insight Backed Regulation")
        self.assertEqual(change["modules"], ["Network", "AI Features"])
        self.assertEqual(change["actions"], ["Update compliance checklist"])
        self.assertEqual(change["knowledge_id"], seeded["knowledge_id"])
        self.assertEqual(change["source_url"], "https://example.com/ai-act")


if __name__ == "__main__":
    unittest.main()
