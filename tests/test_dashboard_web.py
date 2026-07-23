import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from app.run_history import save_run_history
from app.storage.service import StorageService
from app.web.app import create_dashboard_app
from tests.html_test_utils import text_by_testid


class TestDashboardWeb(unittest.TestCase):

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

        old_snapshot = self.store.save_snapshot(
            {
                "source_id": "ec",
                "url": "https://example.com/ec",
                "title": "European Commission",
                "markdown": "# Old version",
                "timestamp": "2026-07-15T10:00:00",
            }
        )
        new_snapshot = self.store.save_snapshot(
            {
                "source_id": "ec",
                "url": "https://example.com/ec",
                "title": "European Commission",
                "markdown": "# New version\nAdded regulation section",
                "timestamp": "2026-07-15T12:00:00",
            }
        )
        saved_diff = self.store.save_diff(
            {
                "source_id": "ec",
                "old_snapshot_id": old_snapshot["id"],
                "new_snapshot_id": new_snapshot["id"],
                "changed": True,
                "added_content": ["Added regulation section"],
                "removed_content": ["Old version"],
                "diff_text": "+Added regulation section",
                "created_at": datetime.now().isoformat(),
            }
        )
        self.diff_id = saved_diff["id"]

        self.store.save_analysis(
            new_snapshot["id"],
            {
                "impact_level": "HIGH",
                "affected_modules": ["Network", "AI Features"],
                "reason": "New cybersecurity requirements affect connected TVs.",
                "recommended_actions": ["Review OTA security controls"],
                "confidence": "HIGH",
            },
        )

        save_run_history(
            [{"status": "analyzed", "diff_id": self.diff_id}],
            history_file=self.history_file,
        )

        self.client = TestClient(
            create_dashboard_app(
                storage_service=self.store,
                history_file=self.history_file,
                reports_dir=self.reports_dir,
            )
        )

        self.monitor = {
            "id": "ec",
            "name": "European Commission",
            "url": "https://example.com/ec",
            "keywords": ["EU Regulation", "cybersecurity"],
            "category": "EU Policy",
            "frequency": "daily",
            "enabled": True,
        }

    def tearDown(self):
        if getattr(self, "client", None) is not None:
            self.client.close()
        self.client = None
        self.store = None
        self.temp_dir.cleanup()

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_homepage_returns_200_with_stat_cards(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Total Monitors", content)
        self.assertIn(b"Configured monitoring sources", content)
        self.assertIn(b"Today's Changes", content)
        self.assertIn(b"Detected today", content)
        self.assertIn(b">HIGH<", content)
        self.assertIn(b"Immediate attention required", content)
        self.assertIn(b">MEDIUM<", content)
        self.assertIn(b"Review recommended", content)
        self.assertIn(b">LOW<", content)
        self.assertIn(b"For reference", content)
        self.assertIn(b"Recent Activity", content)
        self.assertIn(b"Last monitoring run", content)
        self.assertIn(b"Latest report", content)
        self.assertIn(b"Changed regulations", content)
        self.assertNotIn(b"Last Run Details", content)
        self.assertIn(b'nav-link active', content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_dashboard_summary_cards_link_to_pages(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertIn('href="/monitors"', content)
        self.assertIn('href="/changes"', content)
        self.assertIn('href="/changes?impact=HIGH"', content)
        self.assertIn('href="/changes?impact=MEDIUM"', content)
        self.assertIn('href="/changes?impact=LOW"', content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_dashboard_zero_risk_cards_use_neutral_styling(
        self,
        mock_load_monitors,
    ):
        mock_load_monitors.return_value = [self.monitor]

        with mock.patch(
            "app.web.app._count_changes_by_impact",
            return_value={"HIGH": 1, "MEDIUM": 0, "LOW": 0},
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertIn("dashboard-risk-card risk-high", content)
        self.assertIn("dashboard-risk-card risk-neutral", content)
        self.assertRegex(content, r'risk-label fw-semibold">HIGH</div>')
        self.assertRegex(content, r'risk-label fw-semibold">MEDIUM</div>')
        self.assertRegex(content, r'risk-label fw-semibold">LOW</div>')
        self.assertRegex(content, r'risk-count display-6 mt-2">1</div>')
        self.assertRegex(content, r'risk-count display-6 mt-2">0</div>')
        self.assertNotIn("dashboard-risk-card risk-medium", content)
        self.assertNotIn("dashboard-risk-card risk-low", content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_dashboard_active_risk_cards_use_semantic_classes(
        self,
        mock_load_monitors,
    ):
        mock_load_monitors.return_value = [self.monitor]

        with mock.patch(
            "app.web.app._count_changes_by_impact",
            return_value={"HIGH": 2, "MEDIUM": 1, "LOW": 3},
        ):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertIn("dashboard-risk-card risk-high", content)
        self.assertIn("dashboard-risk-card risk-medium", content)
        self.assertIn("dashboard-risk-card risk-low", content)
        self.assertRegex(content, r'risk-label fw-semibold">HIGH</div>')
        self.assertRegex(content, r'risk-count display-6 mt-2">2</div>')
        self.assertRegex(content, r'risk-label fw-semibold">MEDIUM</div>')
        self.assertRegex(content, r'risk-count display-6 mt-2">1</div>')
        self.assertRegex(content, r'risk-label fw-semibold">LOW</div>')
        self.assertRegex(content, r'risk-count display-6 mt-2">3</div>')
        self.assertNotIn("text-dark", content)
        self.assertNotIn("link-dark", content)
        self.assertIn('href="/changes?impact=HIGH"', content)
        self.assertIn('href="/changes?impact=MEDIUM"', content)
        self.assertIn('href="/changes?impact=LOW"', content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_dashboard_recent_activity_shows_run_and_status(
        self,
        mock_load_monitors,
    ):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertIn("Completed successfully", content)
        self.assertEqual(
            text_by_testid(content, "dashboard-monitoring-status"),
            "Completed successfully",
        )
        self.assertEqual(text_by_testid(content, "dashboard-changed-regulations"), "1")
        self.assertEqual(text_by_testid(content, "dashboard-latest-report"), "N/A")
        self.assertIn('data-testid="dashboard-last-monitoring-run"', content)
        self.assertIn('data-testid="dashboard-changed-regulations"', content)
        self.assertIn('data-testid="dashboard-latest-report"', content)
        self.assertIn('data-testid="dashboard-monitoring-status"', content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_dashboard_risk_cards_link_to_filtered_changes(
        self,
        mock_load_monitors,
    ):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        content = response.text
        self.assertIn('href="/changes?impact=HIGH"', content)
        self.assertIn('href="/changes?impact=MEDIUM"', content)
        self.assertIn('href="/changes?impact=LOW"', content)
        self.assertIn('aria-label="View high risk changes"', content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_dashboard_high_risk_drilldown_to_detail(
        self,
        mock_load_monitors,
    ):
        mock_load_monitors.return_value = [self.monitor]

        filtered = self.client.get("/changes?impact=HIGH")
        self.assertEqual(filtered.status_code, 200)
        self.assertIn(b"European Commission", filtered.content)
        self.assertIn(b"text-bg-danger", filtered.content)
        self.assertIn(b'value="HIGH"', filtered.content)

        detail = self.client.get(f"/detail/{self.diff_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"Change Detail", detail.content)
        self.assertIn(b"New cybersecurity requirements", detail.content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_changes_page_renders_with_filters_and_badges(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/changes")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Keyword Search", content)
        self.assertIn(b"Impact Level", content)
        self.assertIn(b"European Commission", content)
        self.assertIn(b"text-bg-danger", content)
        self.assertIn(b"Network", content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_changes_page_supports_impact_filter(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/changes?impact=HIGH")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"European Commission", response.content)

        response_none = self.client.get("/changes?impact=NONE")
        self.assertEqual(response_none.status_code, 200)
        self.assertIn(b"No regulation changes match your filters.", response_none.content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_changes_page_supports_keyword_search(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/changes?q=cybersecurity")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"European Commission", response.content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_detail_page_renders_formatted_sections(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get(f"/detail/{self.diff_id}")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Impact Analysis", content)
        self.assertIn(b"Recommended Actions", content)
        self.assertIn(b"Diff Content", content)
        self.assertIn(b"Added", content)
        self.assertIn(b"Removed", content)
        self.assertIn(b"Added regulation section", content)
        self.assertIn(b"Review OTA security controls", content)
        self.assertIn(b"New cybersecurity requirements affect connected TVs.", content)
        self.assertIn(b"Regulation Extraction", content)
        self.assertIn(b"No regulation extraction available for this change.", content)

    def _regulation_extraction_payload(self) -> dict:
        return {
            "title": "EU Cybersecurity Regulation Update",
            "publish_date": "2026-05-07",
            "summary": "New cybersecurity obligations for connected devices.",
            "category": "Cybersecurity",
            "regulation_type": "AMENDMENT",
            "effective_date": "2028-08-02",
            "affected_countries": ["EU"],
            "affected_products": ["Smart TV"],
            "affected_modules": ["Network", "Cybersecurity controls"],
            "key_requirements": ["Assess connected device security"],
            "actions_required": ["Update compliance checklist"],
            "is_regulation_content": True,
            "confidence": "HIGH",
        }

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_detail_page_renders_regulation_extraction(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]
        latest_snapshot = self.store.get_latest_snapshot("ec")

        self.store.save_analysis(
            latest_snapshot["id"],
            {
                "impact_level": "HIGH",
                "affected_modules": ["Network", "AI Features"],
                "reason": "New cybersecurity requirements affect connected TVs.",
                "recommended_actions": ["Review OTA security controls"],
                "confidence": "HIGH",
                "regulation_extraction": self._regulation_extraction_payload(),
            },
        )

        response = self.client.get(f"/detail/{self.diff_id}")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Regulation Extraction", content)
        self.assertIn(b"EU Cybersecurity Regulation Update", content)
        self.assertIn(b"AMENDMENT", content)
        self.assertIn(b"2026-05-07", content)
        self.assertIn(b"2028-08-02", content)
        self.assertIn(b"New cybersecurity obligations for connected devices.", content)
        self.assertIn(b"Smart TV", content)
        self.assertIn(b"Assess connected device security", content)
        self.assertIn(b"Update compliance checklist", content)
        self.assertIn(b"Regulation Content", content)
        self.assertNotIn(
            b"No regulation extraction available for this change.",
            content,
        )

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_detail_page_legacy_analysis_without_regulation_extraction(
        self,
        mock_load_monitors,
    ):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get(f"/detail/{self.diff_id}")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Regulation Extraction", content)
        self.assertIn(
            b"No regulation extraction available for this change.",
            content,
        )
        self.assertNotIn(b"EU Cybersecurity Regulation Update", content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_detail_page_renders_evidence_section(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]
        latest_snapshot = self.store.get_latest_snapshot("ec")

        self.store.save_analysis(
            latest_snapshot["id"],
            {
                "impact_level": "HIGH",
                "affected_modules": ["Network", "AI Features"],
                "reason": "New cybersecurity requirements affect connected TVs.",
                "recommended_actions": ["Review OTA security controls"],
                "confidence": "HIGH",
                "evidence": [
                    {
                        "source_id": "ec",
                        "name": "European Commission",
                        "url": "https://example.com/ec",
                        "snapshot_id": latest_snapshot["id"],
                        "diff_id": self.diff_id,
                        "timestamp": "2026-07-15T12:00:00",
                    }
                ],
            },
        )

        response = self.client.get(f"/detail/{self.diff_id}")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Source References", content)
        self.assertIn(b"Snapshot ID", content)
        self.assertIn(b"Diff ID", content)
        self.assertIn(b"Parent Monitor", content)
        self.assertIn(b"Open Original Page", content)
        self.assertIn(b"View Diff", content)
        self.assertIn(b"https://example.com/ec", content)
        self.assertIn(str(self.diff_id).encode(), content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_detail_page_renders_multiple_source_references(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]
        latest_snapshot = self.store.get_latest_snapshot("ec")

        self.store.save_analysis(
            latest_snapshot["id"],
            {
                "impact_level": "HIGH",
                "affected_modules": ["Network"],
                "reason": "Multiple pages changed.",
                "recommended_actions": ["Review both pages"],
                "confidence": "HIGH",
                "evidence": [
                    {
                        "source_id": "ec",
                        "parent_monitor_id": "ec",
                        "name": "European Commission",
                        "url": "https://example.com/ec",
                        "snapshot_id": latest_snapshot["id"],
                        "diff_id": self.diff_id,
                        "timestamp": "2026-07-15T12:00:00",
                        "discovered_depth": 0,
                    },
                    {
                        "source_id": "ec",
                        "parent_monitor_id": "ec",
                        "name": "AI Act Policy",
                        "url": "https://example.com/ec/ai-act",
                        "snapshot_id": 99,
                        "diff_id": 100,
                        "timestamp": "2026-07-15T13:00:00",
                        "discovered_depth": 1,
                    },
                ],
            },
        )

        response = self.client.get(f"/detail/{self.diff_id}")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Main Page", content)
        self.assertIn(b"Discovered Page", content)
        self.assertIn(b"AI Act Policy", content)
        self.assertIn(b"https://example.com/ec/ai-act", content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_detail_page_legacy_analysis_fallback(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get(f"/detail/{self.diff_id}")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Source References", content)
        self.assertIn(b"European Commission", content)
        self.assertIn(b"Main Page", content)
        self.assertIn(b"Parent Monitor", content)
        self.assertIn(b"Open Original Page", content)
        self.assertIn(b"View Diff", content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_changes_page_shows_changed_pages_and_source_urls(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        old_snapshot_two = self.store.save_snapshot(
            {
                "source_id": "ec",
                "url": "https://example.com/ec/ai-act",
                "title": "AI Act Policy",
                "markdown": "# Old AI Act",
                "timestamp": "2026-07-15T09:00:00",
            }
        )
        new_snapshot_two = self.store.save_snapshot(
            {
                "source_id": "ec",
                "url": "https://example.com/ec/ai-act",
                "title": "AI Act Policy",
                "markdown": "# New AI Act\nAdded section",
                "timestamp": "2026-07-15T13:00:00",
            }
        )
        self.store.save_diff(
            {
                "source_id": "ec",
                "old_snapshot_id": old_snapshot_two["id"],
                "new_snapshot_id": new_snapshot_two["id"],
                "changed": True,
                "added_content": ["Added section"],
                "removed_content": ["Old AI Act"],
                "diff_text": "+Added section",
                "created_at": datetime.now().isoformat(),
            }
        )
        self.store.save_analysis(
            new_snapshot_two["id"],
            {
                "impact_level": "MEDIUM",
                "affected_modules": ["AI Features"],
                "reason": "Discovered page changed.",
                "recommended_actions": ["Review AI Act page"],
                "confidence": "MEDIUM",
                "evidence": [
                    {
                        "source_id": "ec",
                        "parent_monitor_id": "ec",
                        "name": "AI Act Policy",
                        "url": "https://example.com/ec/ai-act",
                        "snapshot_id": new_snapshot_two["id"],
                        "discovered_depth": 1,
                    }
                ],
            },
        )

        response = self.client.get("/changes")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"2 changed page(s)", content)
        self.assertIn(b"2 source URL(s)", content)
        self.assertIn(b"https://example.com/ec/ai-act", content)
        self.assertIn(b"Child page", content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_monitors_page_shows_management_and_summary(
        self,
        mock_load_monitors,
    ):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/monitors")

        self.assertEqual(response.status_code, 200)
        content = response.content
        self.assertIn(b"Monitors", content)
        self.assertIn(b"+ Add Monitor", content)
        self.assertIn(b"Total Monitors", content)
        self.assertIn(b"Enabled", content)
        self.assertIn(b"Disabled", content)
        self.assertIn(b"Recent Updates", content)
        self.assertIn(b'href="/monitors"', content)
        self.assertNotIn(b"Monitoring Targets", content)
        self.assertNotIn(b"Manage Monitors", content)

    @mock.patch("app.web.app.load_monitors", autospec=True)
    def test_manage_monitors_redirects_to_monitors(self, mock_load_monitors):
        mock_load_monitors.return_value = [self.monitor]

        response = self.client.get("/manage-monitors", follow_redirects=False)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["location"], "/monitors")


if __name__ == "__main__":
    unittest.main()
