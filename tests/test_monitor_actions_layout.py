import gc
import json
import re
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.monitors.repository import MonitorRepository, reset_monitor_repository
from app.monitors.run_store import reset_monitor_run_store
from app.storage.service import StorageService
from app.web.app import create_dashboard_app


def _extract_css_rule_block(html: str, selector_snippet: str, *, occurrence: int = -1) -> str:
    pattern = rf"([^{{]*{re.escape(selector_snippet)}[^{{]*)\{{([^}}]+)\}}"
    matches = list(re.finditer(pattern, html, flags=re.DOTALL))
    if not matches:
        return ""
    return matches[occurrence].group(2)


def _extract_css_rule_block_containing(
    html: str,
    selector_snippet: str,
    *needles: str,
) -> str:
    pattern = rf"([^{{]*{re.escape(selector_snippet)}[^{{]*)\{{([^}}]+)\}}"
    for match in re.finditer(pattern, html, flags=re.DOTALL):
        block = match.group(2)
        if all(needle in block for needle in needles):
            return block
    return ""


def _parse_px_values(rule_block: str, property_name: str) -> list[int]:
    return [
        int(value)
        for value in re.findall(rf"{re.escape(property_name)}:\s*(\d+)px", rule_block)
    ]


class MonitorActionsLayoutTests(unittest.TestCase):
    def setUp(self):
        reset_monitor_repository()
        reset_monitor_run_store()
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        base_path = Path(self.temp_dir.name)
        self.db_path = base_path / "storage.db"
        self.seed_file = base_path / "monitors.json"
        self.seed_file.write_text(
            json.dumps({"monitors": []}),
            encoding="utf-8",
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
        if getattr(self, "client", None) is not None:
            self.client.close()
        reset_monitor_repository()
        reset_monitor_run_store()
        gc.collect()
        self.temp_dir.cleanup()

    def _page_html(self) -> str:
        response = self.client.get("/monitors")
        self.assertEqual(response.status_code, 200)
        return response.text

    def test_rendered_page_includes_ui_version_marker(self):
        html = self._page_html()
        self.assertIn(
            '<meta name="monitor-ui-version" content="actions-layout-v4-sticky-body-dropdown">',
            html,
        )

    def test_actions_column_css_minimum_width_is_at_least_190px(self):
        html = self._page_html()
        rule_block = _extract_css_rule_block_containing(
            html,
            "table.monitor-table th.monitor-actions-column",
            "position: sticky",
        )
        self.assertTrue(rule_block, "Expected actions-layout-v4 CSS block in rendered page")
        min_widths = _parse_px_values(rule_block, "min-width")
        widths = _parse_px_values(rule_block, "width")
        self.assertTrue(min_widths, "Expected min-width on monitor actions column")
        self.assertGreaterEqual(max(min_widths), 190)
        self.assertGreaterEqual(max(widths), 190)

    def test_action_buttons_use_intrinsic_flex_width(self):
        html = self._page_html()
        rule_block = _extract_css_rule_block(html, "table.monitor-table .monitor-action-buttons")
        self.assertIn("flex-wrap: nowrap", rule_block)
        self.assertIn("width: max-content", rule_block)
        self.assertIn("min-width: max-content", rule_block)
        self.assertIn("align-items: center", rule_block)
        self.assertIn("justify-content: center", rule_block)

    def test_actions_cell_has_right_padding_override(self):
        html = self._page_html()
        rule_block = _extract_css_rule_block(html, "table.monitor-table td.monitor-actions")
        self.assertTrue(rule_block, "Expected td.monitor-actions CSS block")
        self.assertIn("padding-right: 8px !important", rule_block)

    def test_sticky_actions_column_css(self):
        html = self._page_html()
        rule_block = _extract_css_rule_block_containing(
            html,
            "table.monitor-table th.monitor-actions-column",
            "position: sticky",
        )
        self.assertIn("position: sticky", rule_block)
        self.assertIn("right: 0", rule_block)
        min_widths = _parse_px_values(rule_block, "min-width")
        widths = _parse_px_values(rule_block, "width")
        self.assertGreaterEqual(max(min_widths), 190)
        self.assertGreaterEqual(max(widths), 190)

    def test_sticky_actions_background_and_z_index(self):
        html = self._page_html()
        body_rule = _extract_css_rule_block(html, "table.monitor-table td.monitor-actions")
        header_rule = _extract_css_rule_block(
            html,
            "table.monitor-table th.monitor-actions-column",
            occurrence=-1,
        )
        self.assertIn("background-color: var(--bs-body-bg)", body_rule)
        self.assertIn("z-index: 3", body_rule)
        self.assertIn("background-color: var(--bs-tertiary-bg)", header_rule)
        self.assertIn("z-index: 4", header_rule)
        self.assertIn(
            "table.monitor-table.table-hover tbody tr:hover td.monitor-actions",
            html,
        )
        self.assertIn("var(--bs-table-hover-bg", html)

    def test_sticky_actions_visual_separator(self):
        html = self._page_html()
        rule_block = _extract_css_rule_block_containing(
            html,
            "table.monitor-table th.monitor-actions-column",
            "position: sticky",
        )
        self.assertTrue(
            "box-shadow:" in rule_block or "border-left:" in rule_block,
            "Expected subtle visual separator on sticky actions column",
        )

    def test_sticky_actions_regression_th_and_td_use_sticky_classes(self):
        html = self._page_html()
        self.assertRegex(
            html,
            r'<th[^>]*class="[^"]*monitor-actions-column[^"]*"[^>]*>\s*Actions\s*</th>',
        )
        self.assertIn('class="monitor-actions"', html)
        shared_rule = _extract_css_rule_block_containing(
            html,
            "table.monitor-table th.monitor-actions-column",
            "position: sticky",
        )
        self.assertIn("position: sticky", shared_rule)
        self.assertIn("right: 0", shared_rule)

    def test_route_renders_monitor_manage_template(self):
        html = self._page_html()
        self.assertIn("Add, edit, or remove monitoring sources", html)
        self.assertIn("renderMonitors", html)
        self.assertIn("monitor-table-scroll monitor-table-wrapper", html)
        self.assertNotIn("Monitoring Targets", html)

    def test_actions_column_uses_stable_class(self):
        html = self._page_html()
        self.assertIn('class="monitor-actions-column"', html)
        self.assertIn('class="monitor-actions"', html)

    def test_actions_template_contains_flex_wrapper_and_controls(self):
        html = self._page_html()
        self.assertIn("monitor-action-buttons", html)
        self.assertIn("monitor-run-button run-monitor-btn", html)
        self.assertIn("monitor-more-toggle", html)
        self.assertIn('data-testid="monitor-actions-${escapeHtml(monitor.id)}"', html)
        self.assertIn('data-testid="monitor-run-${escapeHtml(monitor.id)}"', html)
        self.assertIn('data-testid="monitor-more-${escapeHtml(monitor.id)}"', html)

    def test_more_dropdown_uses_end_alignment_and_viewport_boundary(self):
        html = self._page_html()
        self.assertIn('class="dropdown-menu dropdown-menu-end monitor-more-menu"', html)
        self.assertIn('data-bs-boundary="viewport"', html)

    def test_dropdown_initialization_uses_viewport_boundary_and_fixed_strategy(self):
        html = self._page_html()
        self.assertIn("initMonitorDropdowns", html)
        self.assertIn('boundary: "viewport"', html)
        self.assertIn('strategy: "fixed"', html)
        self.assertIn(".monitor-more-toggle", html)

    def test_dropdown_menu_portals_to_document_body_on_show(self):
        html = self._page_html()
        self.assertIn("monitor-more-menu", html)
        self.assertIn("document.body.appendChild(menu)", html)
        self.assertIn("show.bs.dropdown", html)
        self.assertIn("hidden.bs.dropdown", html)
        self.assertIn("_monitorDropdownHost", html)
        self.assertNotIn("z-index: 1080", html)

    def test_running_state_keeps_more_control_and_stable_button_classes(self):
        html = self._page_html()
        self.assertIn("monitor-run-button", html)
        self.assertIn("is-running", html)
        self.assertIn("monitor-more-toggle", html)
        self.assertIn("monitor-action-buttons", html)

    def test_existing_monitor_action_urls_unchanged(self):
        html = self._page_html()
        self.assertIn('class="dropdown-item edit-monitor-btn"', html)
        self.assertIn('class="dropdown-item toggle-monitor-btn"', html)
        self.assertIn('class="dropdown-item text-danger delete-monitor-btn"', html)
        self.assertIn("/api/monitors", html)
        self.assertIn("fetch(`/api/monitors/${monitorId}/run`", html)


if __name__ == "__main__":
    unittest.main()
