import gc
import json
import tempfile
import unittest
from pathlib import Path

from app.knowledge.builder import build_knowledge_item
from app.knowledge.relationship import (
    build_relationships,
    find_related_regulations,
)
from app.storage.service import StorageService


class TestBuildRelationships(unittest.TestCase):

    def _base_item(self, **overrides) -> dict:
        item = {
            "title": "EU AI Act",
            "category": "AI Regulation",
            "regulation_type": "NEW",
            "publish_date": "2026-01-01",
            "effective_date": "2026-06-01",
            "countries": ["EU"],
            "products": ["Smart TV"],
            "modules": ["AI Features", "Network"],
        }
        item.update(overrides)
        return item

    def test_amendment_detection(self):
        current = self._base_item(
            regulation_type="AMENDMENT",
            publish_date="2027-03-01",
            title="EU AI Act",
        )
        existing = [
            self._base_item(
                id=1,
                regulation_type="NEW",
                publish_date="2026-01-01",
                effective_date="2026-06-01",
                title="EU AI Act",
            )
        ]

        relationships = build_relationships(current, existing)

        self.assertEqual(len(relationships), 1)
        self.assertEqual(relationships[0]["knowledge_id"], 1)
        self.assertEqual(relationships[0]["relation"], "AMENDMENT")
        self.assertGreaterEqual(relationships[0]["confidence"], 0.9)
        self.assertIn("later publish date", relationships[0]["reason"].lower())

    def test_guidance_detection(self):
        current = self._base_item(
            id=10,
            title="EU AI Act Guidance",
            regulation_type="GUIDANCE",
            modules=["AI Features"],
        )
        existing = [
            self._base_item(
                id=2,
                title="EU AI Act",
                regulation_type="NEW",
                modules=["AI Features"],
            )
        ]

        relationships = build_relationships(current, existing)

        self.assertEqual(len(relationships), 1)
        self.assertEqual(relationships[0]["relation"], "GUIDANCE")
        self.assertGreaterEqual(relationships[0]["confidence"], 0.65)

    def test_unrelated_regulations(self):
        current = self._base_item(
            title="Marine Equipment Directive",
            category="Maritime",
            regulation_type="NEW",
            countries=["US"],
            products=["Ship radar"],
            modules=["Navigation"],
        )
        existing = [
            self._base_item(
                id=3,
                title="EU AI Act",
                category="AI Regulation",
                regulation_type="NEW",
                countries=["EU"],
                products=["Smart TV"],
                modules=["AI Features"],
            )
        ]

        relationships = build_relationships(current, existing)

        self.assertEqual(relationships, [])
        self.assertEqual(find_related_regulations(current, existing), [])

    def test_confidence_ordering(self):
        current = self._base_item(
            regulation_type="AMENDMENT",
            publish_date="2028-01-01",
            title="EU AI Act",
        )
        existing = [
            self._base_item(
                id=4,
                title="EU AI Act",
                regulation_type="NEW",
                publish_date="2026-01-01",
                modules=["AI Features"],
            ),
            self._base_item(
                id=5,
                title="EU AI Act Guidance Notes",
                regulation_type="GUIDANCE",
                publish_date="2026-06-01",
                modules=["AI Features"],
            ),
        ]

        relationships = build_relationships(current, existing)

        self.assertGreaterEqual(len(relationships), 2)
        confidences = [item["confidence"] for item in relationships]
        self.assertEqual(confidences, sorted(confidences, reverse=True))

    def test_skips_self_and_items_without_id(self):
        current = self._base_item(id=6, regulation_type="AMENDMENT")
        existing = [
            self._base_item(id=6, title="EU AI Act"),
            self._base_item(title="EU AI Act"),
        ]

        relationships = build_relationships(current, existing)

        self.assertEqual(relationships, [])

    def test_find_related_regulations_respects_min_confidence(self):
        current = self._base_item(
            regulation_type="AMENDMENT",
            publish_date="2028-01-01",
            title="EU AI Act",
        )
        existing = [
            self._base_item(
                id=7,
                title="EU AI Act",
                regulation_type="NEW",
                publish_date="2026-01-01",
            )
        ]

        related = find_related_regulations(
            current,
            existing,
            min_confidence=0.95,
        )

        self.assertEqual(len(related), 1)
        self.assertGreaterEqual(related[0]["confidence"], 0.95)


class TestRelationshipSerialization(unittest.TestCase):

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

    def test_relationships_persist_in_actions_json_envelope(self):
        relationships = [
            {
                "knowledge_id": 12,
                "relation": "AMENDMENT",
                "confidence": 0.93,
                "reason": "Same regulation title with later publish date",
            }
        ]
        item = {
            "snapshot_id": 1,
            "source_id": "eu_ai_act",
            "title": "EU AI Act Update",
            "category": "AI Regulation",
            "regulation_type": "AMENDMENT",
            "summary": "Updated obligations.",
            "effective_date": "2028-08-02",
            "countries": ["EU"],
            "products": ["Smart TV"],
            "modules": ["AI Features"],
            "requirements": ["Assess embedded high-risk AI systems"],
            "actions": ["Update compliance checklist"],
            "relationships": relationships,
            "confidence": "HIGH",
        }

        saved = self.store.save_knowledge_item(item)
        loaded = self.store.get_knowledge_item(saved["id"])

        self.assertEqual(saved["relationships"], relationships)
        self.assertEqual(loaded["relationships"], relationships)
        self.assertEqual(loaded["actions"], ["Update compliance checklist"])

        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT actions_json FROM knowledge_items WHERE id = ?",
                (saved["id"],),
            ).fetchone()

        payload = json.loads(row["actions_json"])
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["actions"], ["Update compliance checklist"])
        self.assertEqual(payload["relationships"], relationships)

    def test_backward_compatible_actions_only_payload(self):
        with self.store._connect() as connection:
            connection.execute(
                """
                INSERT INTO knowledge_items (
                    snapshot_id,
                    source_id,
                    title,
                    category,
                    regulation_type,
                    summary,
                    effective_date,
                    countries_json,
                    products_json,
                    modules_json,
                    requirements_json,
                    actions_json,
                    confidence,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    1,
                    "legacy",
                    "Legacy Regulation",
                    "AI Regulation",
                    "NEW",
                    "Legacy summary.",
                    "2026-01-01",
                    '["EU"]',
                    '["Smart TV"]',
                    '["Network"]',
                    '["Legacy requirement"]',
                    '["Legacy action"]',
                    "HIGH",
                    "2026-01-01T00:00:00",
                ),
            )

        loaded = self.store.get_knowledge_item(1)

        self.assertEqual(loaded["actions"], ["Legacy action"])
        self.assertEqual(loaded["relationships"], [])

    def test_builder_attaches_relationships_from_existing_items(self):
        first = self.store.save_knowledge_item(
            {
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
        )

        snapshot = {"id": 2, "source_id": "eu_ai_act"}
        monitor = {"id": "eu_ai_act", "category": "AI Regulation"}
        analysis = {
            "regulation_extraction": {
                "title": "EU AI Act",
                "summary": "Amended obligations.",
                "regulation_type": "AMENDMENT",
                "publish_date": "2027-03-01",
                "effective_date": "2028-08-02",
                "affected_countries": ["EU"],
                "affected_products": ["Smart TV"],
                "affected_modules": ["AI Features"],
                "key_requirements": ["Updated assessment scope"],
                "actions_required": ["Update compliance checklist"],
                "confidence": "HIGH",
            }
        }

        built = build_knowledge_item(
            snapshot,
            monitor,
            analysis,
            existing_items=[first],
        )

        self.assertIsNotNone(built)
        self.assertGreater(len(built["relationships"]), 0)
        self.assertEqual(built["relationships"][0]["knowledge_id"], first["id"])
        self.assertEqual(built["relationships"][0]["relation"], "AMENDMENT")


if __name__ == "__main__":
    unittest.main()
