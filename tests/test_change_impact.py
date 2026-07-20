import gc
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app.run_history import save_run_history
from app.storage.service import StorageService
from app.web.app import create_dashboard_app
from app.web.change_helper import (
    count_changes_by_impact,
    filter_changes_by_impact,
    get_change_impact,
    normalize_impact,
    normalized_change_impact,
)


class TestChangeImpactHelper(unittest.TestCase):

    def test_normalize_impact_handles_case_and_whitespace(self):
        self.assertEqual(normalize_impact("LOW"), "LOW")
        self.assertEqual(normalize_impact(" low "), "LOW")
        self.assertEqual(normalize_impact("Low"), "LOW")
        self.assertEqual(normalize_impact("HIGH"), "HIGH")
        self.assertEqual(normalize_impact("medium"), "MEDIUM")
        self.assertEqual(normalize_impact(""), "NONE")
        self.assertEqual(normalize_impact("critical"), "UNKNOWN")

    def test_get_change_impact_reads_nested_analysis_fields(self):
        self.assertEqual(
            get_change_impact(
                {
                    "analysis": {"impact_level": "Low"},
                }
            ),
            "Low",
        )
        self.assertEqual(
            get_change_impact(
                {
                    "impact": "HIGH",
                    "analysis": {"impact_level": "LOW"},
                }
            ),
            "LOW",
        )
        self.assertEqual(
            get_change_impact({"impact_level": "MEDIUM"}),
            "MEDIUM",
        )


class TestDashboardChangeImpactAlignment(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(
            ignore_cleanup_errors=True
        )
        base_path = Path(self.temp_dir.name)
        self.history_file = base_path / "run_history.json"
        self.reports_dir = base_path / "reports"
        self.store = StorageService(
            db_path=base_path / "storage.db",
            raw_dir=base_path / "raw",
            meta_file=base_path / "snapshots.json",
        )

        self.monitor = {
            "id": "ec",
            "name": "European Commission",
            "url": "https://example.com/ec",
            "keywords": ["EU Regulation"],
            "category": "EU Policy",
            "frequency": "daily",
            "enabled": True,
        }

        self.client = TestClient(
            create_dashboard_app(
                storage_service=self.store,
                history_file=self.history_file,
                reports_dir=self.reports_dir,
            )
        )

    def tearDown(self):
        self.client = None
        self.store = None
        gc.collect()
        self.temp_dir.cleanup()

    def _seed_displayable_change(
        self,
        *,
        impact_level: str,
        source_id: str = "ec",
    ) -> dict:
        old_snapshot = self.store.save_snapshot(
            {
                "source_id": source_id,
                "url": f"https://example.com/{source_id}",
                "title": source_id,
                "markdown": "# Old version",
                "timestamp": "2026-07-15T10:00:00",
            }
        )
        new_snapshot = self.store.save_snapshot(
            {
                "source_id": source_id,
                "url": f"https://example.com/{source_id}",
                "title": source_id,
                "markdown": "# New version",
                "timestamp": "2026-07-15T12:00:00",
            }
        )
        saved_diff = self.store.save_diff(
            {
                "source_id": source_id,
                "old_snapshot_id": old_snapshot["id"],
                "new_snapshot_id": new_snapshot["id"],
                "changed": True,
                "added_content": ["Added section"],
                "removed_content": ["Old version"],
                "diff_text": "+Added section",
                "created_at": datetime.now().isoformat(),
            }
        )
        self.store.save_analysis(
            new_snapshot["id"],
            {
                "impact_level": impact_level,
                "affected_modules": ["Network"],
                "reason": f"{impact_level} impact detected.",
                "recommended_actions": ["Review controls"],
                "confidence": "HIGH",
            },
        )
        return saved_diff

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_low_dashboard_count_matches_changes_filter(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]
        low_diff = self._seed_displayable_change(impact_level="LOW")

        dashboard = self.client.get("/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertRegex(
            dashboard.text,
            r">LOW</div>\s*<div class=\"text-muted small\">For reference</div>\s*<div class=\"display-6 mt-2 text-success\">1</div>",
        )

        filtered = self.client.get("/changes?impact=LOW")
        self.assertEqual(filtered.status_code, 200)
        self.assertIn(b"European Commission", filtered.content)
        self.assertIn(
            f'href="/detail/{low_diff["id"]}"'.encode(),
            filtered.content,
        )

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_low_filter_normalizes_query_values(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]
        self._seed_displayable_change(impact_level="Low")

        for query in ("LOW", "low", " Low "):
            with self.subTest(query=query):
                response = self.client.get(f"/changes?impact={query.strip()}")
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"European Commission", response.content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_orphan_low_analysis_is_not_counted_on_dashboard(
        self,
        mock_load_monitors,
    ):
        mock_load_monitors.return_value = [self.monitor]

        orphan_snapshot = self.store.save_snapshot(
            {
                "source_id": "orphan",
                "url": "https://example.com/orphan",
                "title": "Orphan Source",
                "markdown": "# Orphan",
                "timestamp": "2026-07-15T12:00:00",
            }
        )
        self.store.save_analysis(
            orphan_snapshot["id"],
            {"impact_level": "LOW"},
        )

        high_diff = self._seed_displayable_change(impact_level="HIGH")

        dashboard = self.client.get("/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertRegex(
            dashboard.text,
            r'fw-semibold text-secondary">LOW</div>\s*<div class="text-muted small">For reference</div>\s*<div class="display-6 mt-2 text-secondary">0</div>',
        )

        filtered_low = self.client.get("/changes?impact=LOW")
        self.assertNotIn(b"European Commission", filtered_low.content)

        filtered_high = self.client.get("/changes?impact=HIGH")
        self.assertIn(b"European Commission", filtered_high.content)
        self.assertIn(
            f'href="/detail/{high_diff["id"]}"'.encode(),
            filtered_high.content,
        )

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_high_and_medium_counts_remain_aligned(self, mock_load_monitors):
        mock_load_monitors.return_value = [
            self.monitor,
            {
                **self.monitor,
                "id": "eu_red",
                "name": "EU RED",
                "url": "https://example.com/eu_red",
            },
        ]
        high_diff = self._seed_displayable_change(impact_level="HIGH")
        medium_diff = self._seed_displayable_change(
            impact_level="MEDIUM",
            source_id="eu_red",
        )

        dashboard = self.client.get("/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"text-danger", dashboard.content)
        self.assertIn(b"text-warning-emphasis", dashboard.content)

        high_page = self.client.get("/changes?impact=HIGH")
        medium_page = self.client.get("/changes?impact=MEDIUM")

        self.assertIn(
            f'href="/detail/{high_diff["id"]}"'.encode(),
            high_page.content,
        )
        self.assertIn(
            f'href="/detail/{medium_diff["id"]}"'.encode(),
            medium_page.content,
        )

    def test_count_and_filter_use_same_normalized_collection(self):
        changes = [
            {
                "diff_id": 1,
                "impact_level": normalized_change_impact(
                    {"analysis": {"impact_level": " low "}}
                ),
            },
            {
                "diff_id": 2,
                "impact_level": "HIGH",
            },
        ]

        counts = count_changes_by_impact(changes)
        filtered = filter_changes_by_impact(changes, "LOW")

        self.assertEqual(counts["LOW"], 1)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["diff_id"], 1)


if __name__ == "__main__":
    unittest.main()
