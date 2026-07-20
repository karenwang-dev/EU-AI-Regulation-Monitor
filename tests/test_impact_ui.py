import unittest

from app.web.impact_ui import (
    get_dashboard_risk_card_classes,
    get_impact_badge_classes,
    get_impact_ui,
)


class TestImpactUi(unittest.TestCase):

    def test_high_dashboard_classes_when_count_positive(self):
        classes = get_dashboard_risk_card_classes("HIGH", 3)
        self.assertEqual(classes["border_class"], "border-danger")
        self.assertEqual(classes["label_class"], "text-danger")
        self.assertEqual(classes["count_class"], "text-danger")
        self.assertEqual(classes["background_class"], "bg-danger-subtle")

    def test_medium_dashboard_classes_when_count_positive(self):
        classes = get_dashboard_risk_card_classes("MEDIUM", 2)
        self.assertEqual(classes["border_class"], "border-warning")
        self.assertEqual(classes["label_class"], "text-warning-emphasis")
        self.assertEqual(classes["count_class"], "text-warning-emphasis")
        self.assertEqual(classes["background_class"], "bg-warning-subtle")

    def test_low_dashboard_classes_when_count_positive(self):
        classes = get_dashboard_risk_card_classes("LOW", 1)
        self.assertEqual(classes["border_class"], "border-success")
        self.assertEqual(classes["label_class"], "text-success")
        self.assertEqual(classes["count_class"], "text-success")
        self.assertEqual(classes["background_class"], "bg-success-subtle")

    def test_zero_count_uses_neutral_classes(self):
        classes = get_dashboard_risk_card_classes("HIGH", 0)
        self.assertEqual(classes["border_class"], "border-secondary")
        self.assertEqual(classes["label_class"], "text-secondary")
        self.assertEqual(classes["count_class"], "text-secondary")
        self.assertEqual(classes["background_class"], "")

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


if __name__ == "__main__":
    unittest.main()
