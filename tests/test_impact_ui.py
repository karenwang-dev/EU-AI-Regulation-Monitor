import unittest
from pathlib import Path

from app.web.impact_ui import (
    get_dashboard_risk_card_classes,
    get_impact_badge_classes,
    get_impact_ui,
)


class TestImpactUi(unittest.TestCase):

    def test_high_dashboard_classes_when_count_positive(self):
        classes = get_dashboard_risk_card_classes("HIGH", 3)
        self.assertEqual(classes["risk_class"], "risk-high")

    def test_medium_dashboard_classes_when_count_positive(self):
        classes = get_dashboard_risk_card_classes("MEDIUM", 2)
        self.assertEqual(classes["risk_class"], "risk-medium")

    def test_low_dashboard_classes_when_count_positive(self):
        classes = get_dashboard_risk_card_classes("LOW", 1)
        self.assertEqual(classes["risk_class"], "risk-low")

    def test_zero_count_uses_neutral_classes(self):
        for level in ("HIGH", "MEDIUM", "LOW"):
            classes = get_dashboard_risk_card_classes(level, 0)
            self.assertEqual(classes["risk_class"], "risk-neutral")

    def test_impact_badge_classes_match_changes_ui(self):
        self.assertEqual(
            get_impact_badge_classes("HIGH"),
            "badge rounded-pill text-bg-danger",
        )
        self.assertEqual(
            get_impact_badge_classes("MEDIUM"),
            "badge rounded-pill text-bg-warning text-dark",
        )
        self.assertEqual(
            get_impact_badge_classes("LOW"),
            "badge rounded-pill text-bg-success",
        )
        self.assertEqual(
            get_impact_badge_classes("NONE"),
            "badge rounded-pill text-bg-secondary",
        )

    def test_get_impact_ui_returns_shared_mapping(self):
        ui = get_impact_ui("high")
        self.assertEqual(ui["badge_class"], "text-bg-danger")
        self.assertEqual(ui["risk_class"], "risk-high")


class TestDashboardRiskCss(unittest.TestCase):

    def setUp(self):
        self.base_html = (
            Path(__file__).resolve().parents[1]
            / "app"
            / "web"
            / "templates"
            / "base.html"
        ).read_text(encoding="utf-8")

    def test_bootstrap_version_is_documented(self):
        self.assertIn("bootstrap@5.3.3/dist/css/bootstrap.min.css", self.base_html)

    def test_risk_label_and_count_use_semantic_css_variables(self):
        self.assertIn(".dashboard-risk-card .risk-label,", self.base_html)
        self.assertIn(".dashboard-risk-card .risk-count,", self.base_html)
        self.assertIn("color: var(--risk-color) !important;", self.base_html)
        self.assertIn(".stat-card-link:visited .dashboard-risk-card .risk-count,", self.base_html)

    def test_stat_card_link_does_not_force_body_color_on_all_children(self):
        self.assertNotIn("color: inherit", self.base_html)
        self.assertNotIn("color: var(--bs-body-color)", self.base_html)
        self.assertNotIn(".stat-card-link *", self.base_html)

    def test_semantic_risk_classes_are_defined(self):
        for risk_class in ("risk-high", "risk-medium", "risk-low", "risk-neutral"):
            self.assertIn(f".dashboard-risk-card.{risk_class}", self.base_html)


if __name__ == "__main__":
    unittest.main()
