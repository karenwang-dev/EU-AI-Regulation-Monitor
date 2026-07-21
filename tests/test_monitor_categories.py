import gc
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.dev.change_test_site import LOCAL_TEST_MONITOR_ID
from app.monitors.categories import (
    BUILTIN_CATEGORIES,
    CategoryValidationError,
    merge_category_options,
    normalize_category,
)
from app.monitors.display_helpers import format_category_label
from app.monitors.repository import MonitorRepository, reset_monitor_repository
from app.storage.service import StorageService
from app.web.app import create_dashboard_app


class MonitorCategoryTests(unittest.TestCase):
    def setUp(self):
        reset_monitor_repository()
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.db_path = base_path / "storage.db"
        self.seed_file = base_path / "monitors.json"
        self._write_seed(
            {
                "id": LOCAL_TEST_MONITOR_ID,
                "name": "Local Multi-page Change Test",
                "url": "http://127.0.0.1:8080/dev/change-test-site",
                "keywords": ["policy"],
                "category": "national_regulation",
                "frequency": "daily",
                "enabled": True,
                "crawl_mode": "multi_page",
                "max_depth": 1,
                "max_pages": 3,
            }
        )
        self.repository = MonitorRepository(
            db_path=self.db_path,
            seed_file=self.seed_file,
        )
        self.storage = StorageService(
            db_path=self.db_path,
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )
        self.client = TestClient(
            create_dashboard_app(
                storage_service=self.storage,
                monitors_repository=self.repository,
            )
        )

    def tearDown(self):
        self.client = None
        reset_monitor_repository()
        gc.collect()
        self.temp_dir.cleanup()

    def _write_seed(self, monitor: dict) -> None:
        self.seed_file.write_text(
            json.dumps({"monitors": [monitor]}, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_existing_stored_category_returned_by_repository(self):
        categories = self.repository.list_categories()
        self.assertIn("national_regulation", categories)

    def test_list_categories_removes_case_insensitive_duplicates(self):
        self.repository.create(
            {
                "id": "custom_monitor",
                "name": "Custom Monitor",
                "url": "https://example.com/custom",
                "keywords": ["custom"],
                "category": "National_Regulation",
                "frequency": "daily",
                "enabled": True,
                "crawl_mode": "single",
                "max_depth": 0,
                "max_pages": 1,
            }
        )
        categories = self.repository.list_categories()
        lowered = [value.lower() for value in categories]
        self.assertEqual(lowered.count("national_regulation"), 1)

    def test_merge_builtin_and_custom_categories(self):
        options = merge_category_options(
            stored=["smart_tv_compliance", "national_regulation"],
        )
        self.assertEqual(options[0], "eu_regulation")
        self.assertIn("national_regulation", options)
        self.assertIn("smart_tv_compliance", options)
        for builtin in BUILTIN_CATEGORIES:
            self.assertIn(builtin, options)

    def test_merge_includes_current_monitor_category(self):
        options = merge_category_options(
            stored=["national_regulation"],
            current="legacy_custom_category",
        )
        self.assertIn("legacy_custom_category", options)

    def test_normalize_category_rules(self):
        self.assertEqual(normalize_category("National Regulation"), "national_regulation")
        self.assertEqual(normalize_category("national-regulation"), "national_regulation")
        self.assertEqual(normalize_category("  Industry   Standard "), "industry_standard")
        self.assertEqual(normalize_category("EU Regulation"), "eu_regulation")
        self.assertEqual(normalize_category("Smart TV Compliance"), "smart_tv_compliance")
        self.assertEqual(normalize_category("foo__bar"), "foo_bar")

    def test_invalid_empty_category_raises_validation_error(self):
        with self.assertRaises(CategoryValidationError):
            normalize_category("   ")
        with self.assertRaises(CategoryValidationError):
            normalize_category("!!!")

    def test_format_category_labels_with_acronyms(self):
        self.assertEqual(format_category_label("national_regulation"), "National Regulation")
        self.assertEqual(format_category_label("eu_regulation"), "EU Regulation")
        self.assertEqual(format_category_label("ai_act"), "AI Act")
        self.assertEqual(format_category_label("dsa_guidance"), "DSA Guidance")
        self.assertEqual(format_category_label("dma_update"), "DMA Update")
        self.assertEqual(format_category_label("gdpr_notice"), "GDPR Notice")

    def test_edit_form_contains_stored_category_value(self):
        response = self.client.get("/monitors")
        self.assertIn(b'id="monitorCategory"', response.content)
        self.assertIn(b'list="monitorCategoryOptions"', response.content)
        self.assertIn(b"monitorCategoryOptions", response.content)
        self.assertNotIn(b'<option value="AI Regulation">', response.content)

        categories = self.client.get(
            "/api/monitors/categories?current=national_regulation"
        )
        self.assertEqual(categories.status_code, 200)

    def test_categories_api_includes_current_custom_category(self):
        response = self.client.get(
            "/api/monitors/categories?current=legacy_custom_category"
        )
        self.assertEqual(response.status_code, 200)
        values = [item["value"] for item in response.json()["categories"]]
        self.assertIn("legacy_custom_category", values)
        self.assertIn("national_regulation", values)

    def test_monitor_list_and_get_use_same_stored_category(self):
        listed = self.client.get("/api/monitors").json()
        monitor = next(item for item in listed if item["id"] == LOCAL_TEST_MONITOR_ID)
        fetched = self.repository.get_by_id(LOCAL_TEST_MONITOR_ID)
        self.assertEqual(monitor["category"], "national_regulation")
        self.assertEqual(monitor["category"], fetched["category"])

    def test_create_custom_category(self):
        response = self.client.post(
            "/api/monitors",
            json={
                "name": "Smart TV Compliance Monitor",
                "url": "https://example.com/smart-tv",
                "keywords": ["compliance"],
                "category": "Smart TV Compliance",
                "frequency": "daily",
                "crawl_mode": "single",
                "max_depth": 0,
                "max_pages": 1,
                "enabled": True,
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["category"], "smart_tv_compliance")

    def test_update_monitor_to_custom_category(self):
        response = self.client.put(
            f"/api/monitors/{LOCAL_TEST_MONITOR_ID}",
            json={"category": "Industry Standard"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["category"], "industry_standard")

    def test_update_unrelated_field_does_not_clear_category(self):
        response = self.client.put(
            f"/api/monitors/{LOCAL_TEST_MONITOR_ID}",
            json={"name": "Updated Local Test Name"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["category"], "national_regulation")

    def test_invalid_category_returns_validation_error(self):
        response = self.client.post(
            "/api/monitors",
            json={
                "name": "Invalid Category Monitor",
                "url": "https://example.com/invalid",
                "keywords": ["invalid"],
                "category": "   ",
                "frequency": "daily",
                "crawl_mode": "single",
                "max_depth": 0,
                "max_pages": 1,
                "enabled": True,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Category must contain letters or numbers.", response.json()["detail"])

    def test_new_category_becomes_available_as_suggestion(self):
        self.client.post(
            "/api/monitors",
            json={
                "name": "Suggestion Monitor",
                "url": "https://example.com/suggestion",
                "keywords": ["suggest"],
                "category": "Smart TV Compliance",
                "frequency": "daily",
                "crawl_mode": "single",
                "max_depth": 0,
                "max_pages": 1,
                "enabled": True,
            },
        )
        values = [
            item["value"]
            for item in self.client.get("/api/monitors/categories").json()["categories"]
        ]
        self.assertIn("smart_tv_compliance", values)

    def test_category_not_in_builtin_options_still_listed(self):
        self.repository.update(
            LOCAL_TEST_MONITOR_ID,
            {"category": "legacy_custom_category"},
        )
        monitor = self.repository.get_by_id(LOCAL_TEST_MONITOR_ID)
        self.assertEqual(monitor["category"], "legacy_custom_category")
        options = self.repository.get_category_options(
            current="legacy_custom_category"
        )
        self.assertIn("legacy_custom_category", options)


if __name__ == "__main__":
    unittest.main()
