import gc
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.storage.service import (
    StorageService,
    get_knowledge_item,
    get_knowledge_items,
    save_knowledge_item,
    search_knowledge,
)


class TestKnowledgeStorage(unittest.TestCase):

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

    def _sample_item(
        self,
        *,
        title: str = "EU AI Act",
        category: str = "AI Regulation",
        modules: list[str] | None = None,
        summary: str = "Cybersecurity obligations for connected devices.",
        requirements: list[str] | None = None,
    ) -> dict:
        return {
            "snapshot_id": 42,
            "source_id": "eu_ai_act",
            "title": title,
            "category": category,
            "regulation_type": "NEW",
            "summary": summary,
            "effective_date": "2028-08-02",
            "countries": ["EU"],
            "products": ["Smart TV"],
            "modules": modules or ["AI Features", "Network"],
            "requirements": requirements or [
                "Assess embedded high-risk AI systems"
            ],
            "actions": ["Update compliance checklist"],
            "confidence": "HIGH",
        }

    def test_knowledge_table_created(self):
        with self.store._connect() as connection:
            row = connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name = 'knowledge_items'
                """
            ).fetchone()

        self.assertIsNotNone(row)

        with self.store._connect() as connection:
            columns = connection.execute(
                "PRAGMA table_info(knowledge_items)"
            ).fetchall()
            column_names = {column["name"] for column in columns}

        self.assertIn("countries_json", column_names)
        self.assertIn("modules_json", column_names)
        self.assertIn("requirements_json", column_names)

    def test_save_knowledge_item(self):
        saved = self.store.save_knowledge_item(self._sample_item())

        self.assertIsNotNone(saved["id"])
        self.assertEqual(saved["title"], "EU AI Act")
        self.assertEqual(saved["countries"], ["EU"])
        self.assertEqual(saved["modules"], ["AI Features", "Network"])
        self.assertNotIn("countries_json", saved)
        self.assertNotIn("modules_json", saved)

        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT countries_json, modules_json FROM knowledge_items WHERE id = ?",
                (saved["id"],),
            ).fetchone()

        self.assertEqual(json.loads(row["countries_json"]), ["EU"])
        self.assertEqual(
            json.loads(row["modules_json"]),
            ["AI Features", "Network"],
        )

    def test_get_knowledge_item(self):
        saved = self.store.save_knowledge_item(self._sample_item())

        loaded = self.store.get_knowledge_item(saved["id"])

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["id"], saved["id"])
        self.assertEqual(loaded["snapshot_id"], 42)
        self.assertEqual(loaded["source_id"], "eu_ai_act")
        self.assertEqual(loaded["regulation_type"], "NEW")
        self.assertEqual(loaded["countries"], ["EU"])
        self.assertEqual(loaded["products"], ["Smart TV"])
        self.assertEqual(loaded["requirements"], [
            "Assess embedded high-risk AI systems"
        ])
        self.assertEqual(loaded["actions"], ["Update compliance checklist"])
        self.assertEqual(loaded["confidence"], "HIGH")
        self.assertNotIn("countries_json", loaded)

    def test_get_knowledge_items_filter(self):
        self.store.save_knowledge_item(self._sample_item())
        self.store.save_knowledge_item(
            self._sample_item(
                title="RED Directive",
                category="Product Compliance",
                modules=["Radio equipment", "Display"],
                summary="Radio equipment directive update.",
            )
        )
        self.store.save_knowledge_item(
            self._sample_item(
                title="Cybersecurity Act",
                category="AI Regulation",
                modules=["Network", "Cybersecurity controls"],
                summary="Network security requirements.",
            )
        )

        ai_items = self.store.get_knowledge_items(category="AI Regulation")
        self.assertEqual(len(ai_items), 2)
        self.assertTrue(
            all(item["category"] == "AI Regulation" for item in ai_items)
        )

        network_items = self.store.get_knowledge_items(module="Network")
        self.assertEqual(len(network_items), 2)
        titles = {item["title"] for item in network_items}
        self.assertIn("EU AI Act", titles)
        self.assertIn("Cybersecurity Act", titles)
        self.assertTrue(
            all("Network" in item["modules"] for item in network_items)
        )

    def test_search_knowledge(self):
        self.store.save_knowledge_item(
            self._sample_item(
                title="EU Cybersecurity Framework",
                summary="Framework for device cybersecurity.",
                requirements=["Implement cybersecurity controls"],
                modules=["Network"],
            )
        )
        self.store.save_knowledge_item(
            self._sample_item(
                title="Energy Label Regulation",
                summary="Energy efficiency for displays.",
                requirements=["Update energy label documentation"],
                modules=["Display"],
            )
        )

        title_results = self.store.search_knowledge("Cybersecurity Framework")
        self.assertEqual(len(title_results), 1)
        self.assertEqual(title_results[0]["title"], "EU Cybersecurity Framework")

        summary_results = self.store.search_knowledge("device cybersecurity")
        self.assertEqual(len(summary_results), 1)
        self.assertEqual(summary_results[0]["title"], "EU Cybersecurity Framework")

        requirement_results = self.store.search_knowledge("cybersecurity controls")
        self.assertEqual(len(requirement_results), 1)
        self.assertEqual(
            requirement_results[0]["title"],
            "EU Cybersecurity Framework",
        )

        module_results = self.store.search_knowledge("Network")
        self.assertEqual(len(module_results), 1)
        self.assertIn("Network", module_results[0]["modules"])

    @patch("app.storage.service._default_service", None)
    def test_module_level_wrappers(self):
        temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        base_path = Path(temp_dir.name)
        patched_store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )

        try:
            with patch(
                "app.storage.service._get_service",
                return_value=patched_store,
            ):
                saved = save_knowledge_item(self._sample_item())

                loaded = get_knowledge_item(saved["id"])
                self.assertEqual(loaded["title"], "EU AI Act")

                items = get_knowledge_items(category="AI Regulation")
                self.assertEqual(len(items), 1)

                results = search_knowledge("EU AI Act")
                self.assertEqual(len(results), 1)
        finally:
            patched_store = None
            gc.collect()
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
