import gc
import tempfile
import unittest
from pathlib import Path

from app.storage.service import StorageService
from app.web.knowledge_helper import (
    format_confidence_percent,
    get_relation_badge_class,
    resolve_related_regulations,
)


class TestKnowledgeHelper(unittest.TestCase):

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

    def _sample_item(self, **overrides) -> dict:
        item = {
            "snapshot_id": 1,
            "source_id": "eu_ai_act",
            "title": "EU AI Act",
            "category": "AI Regulation",
            "regulation_type": "NEW",
            "summary": "Original obligations.",
            "effective_date": "2026-06-01",
            "countries": ["EU"],
            "products": ["Smart TV"],
            "modules": ["AI Features"],
            "requirements": ["Assess embedded high-risk AI systems"],
            "actions": ["Initial compliance review"],
            "confidence": "HIGH",
        }
        item.update(overrides)
        return item

    def test_format_confidence_percent(self):
        self.assertEqual(format_confidence_percent(0.93), 93)
        self.assertEqual(format_confidence_percent(0.925), 92)
        self.assertEqual(format_confidence_percent("0.5"), 50)
        self.assertEqual(format_confidence_percent("invalid"), 0)

    def test_relation_badge_classes(self):
        self.assertEqual(get_relation_badge_class("AMENDMENT"), "text-bg-danger")
        self.assertEqual(get_relation_badge_class("GUIDANCE"), "text-bg-warning text-dark")
        self.assertEqual(get_relation_badge_class("IMPLEMENTATION"), "text-bg-primary")
        self.assertEqual(get_relation_badge_class("RELATED"), "text-bg-success")
        self.assertEqual(get_relation_badge_class("REPLACED_BY"), "text-bg-dark")
        self.assertEqual(
            get_relation_badge_class("SUPERSEDES"),
            "badge-relation-supersedes",
        )
        self.assertEqual(get_relation_badge_class("UNKNOWN"), "text-bg-secondary")

    def test_resolve_related_regulations(self):
        related = self.store.save_knowledge_item(
            self._sample_item(title="EU AI Act Original")
        )
        current = {
            "id": 99,
            "title": "EU AI Act Update",
            "relationships": [
                {
                    "knowledge_id": related["id"],
                    "relation": "AMENDMENT",
                    "confidence": 0.93,
                    "reason": "Same regulation title with later publish date",
                }
            ],
        }

        resolved = resolve_related_regulations(current, self.store)

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["knowledge_id"], related["id"])
        self.assertEqual(resolved[0]["title"], "EU AI Act Original")
        self.assertEqual(resolved[0]["relation"], "AMENDMENT")
        self.assertEqual(resolved[0]["confidence"], 0.93)
        self.assertEqual(resolved[0]["confidence_percent"], 93)
        self.assertEqual(
            resolved[0]["reason"],
            "Same regulation title with later publish date",
        )
        self.assertEqual(resolved[0]["badge_class"], "text-bg-danger")
        self.assertEqual(resolved[0]["detail_url"], f"/knowledge/{related['id']}")

    def test_resolve_related_regulations_ignores_missing_items(self):
        current = {
            "id": 1,
            "relationships": [
                {
                    "knowledge_id": 99999,
                    "relation": "RELATED",
                    "confidence": 0.7,
                    "reason": "Missing target",
                }
            ],
        }

        resolved = resolve_related_regulations(current, self.store)

        self.assertEqual(resolved, [])

    def test_resolve_related_regulations_empty_relationships(self):
        current = {"id": 1, "title": "Standalone Regulation"}

        resolved = resolve_related_regulations(current, self.store)

        self.assertEqual(resolved, [])


if __name__ == "__main__":
    unittest.main()
