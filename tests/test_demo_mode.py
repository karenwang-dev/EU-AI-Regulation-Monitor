import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.demo.demo_loader import (
    build_demo_knowledge_item,
    build_demo_monitoring_result,
    build_demo_summary,
    load_demo_analysis,
    load_demo_config,
    load_demo_report,
    load_demo_snapshot,
)


class TestDemoConfig(unittest.TestCase):

    def test_load_demo_config_defaults_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = load_demo_config(
                config_file=Path(temp_dir) / "missing-demo.json"
            )

        self.assertFalse(config["enabled"])

    def test_load_demo_config_reads_enabled_flag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "demo.json"
            config_path.write_text(
                json.dumps({"enabled": True}),
                encoding="utf-8",
            )

            config = load_demo_config(config_file=config_path)

        self.assertTrue(config["enabled"])


class TestDemoLoader(unittest.TestCase):

    def setUp(self):
        self.repo_demo_dir = Path(__file__).resolve().parents[1] / "data" / "demo"

    def test_load_demo_snapshot(self):
        snapshot = load_demo_snapshot(demo_dir=self.repo_demo_dir)

        self.assertEqual(snapshot["source_id"], "eu_ai_act")
        self.assertIn("title", snapshot)

    def test_load_demo_analysis(self):
        analysis = load_demo_analysis(demo_dir=self.repo_demo_dir)

        self.assertEqual(analysis["impact_level"], "MEDIUM")
        self.assertIn("affected_modules", analysis)

    def test_load_demo_report(self):
        report = load_demo_report(demo_dir=self.repo_demo_dir)

        self.assertEqual(report["id"], "2026-07-16_weekly_report_demo")
        self.assertIn("summary", report)

    def test_build_demo_summary_composes_all_sections(self):
        summary = build_demo_summary(demo_dir=self.repo_demo_dir)

        self.assertIn("config", summary)
        self.assertIn("monitoring_result", summary)
        self.assertIn("analysis", summary)
        self.assertIn("knowledge_item", summary)
        self.assertIn("report", summary)
        self.assertEqual(summary["monitoring_result"]["status"], "analyzed")
        self.assertEqual(summary["knowledge_item"]["source_id"], "eu_ai_act")

    def test_build_demo_helpers_with_custom_data(self):
        snapshot = {
            "id": 99,
            "source_id": "test_source",
            "title": "Test Regulation",
            "created_at": "2026-07-16T10:00:00",
            "url": "https://example.com/test",
        }
        analysis = {
            "impact_level": "LOW",
            "affected_modules": ["Network"],
            "reason": "Test reason",
            "recommended_actions": ["Review policy"],
            "confidence": "MEDIUM",
        }

        monitoring = build_demo_monitoring_result(snapshot, analysis)
        knowledge = build_demo_knowledge_item(snapshot, analysis)

        self.assertEqual(monitoring["source_id"], "test_source")
        self.assertEqual(knowledge["modules"], ["Network"])


class TestDemoCli(unittest.TestCase):

    def test_cli_demo_command(self):
        import main

        exit_code = main.run_demo()

        self.assertEqual(exit_code, 0)

    def test_cli_demo_entrypoint(self):
        result = subprocess.run(
            [sys.executable, "main.py", "demo"],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Demo Mode", result.stdout)
        self.assertIn("Sample Monitoring Result", result.stdout)
        self.assertIn("AI Impact Analysis", result.stdout)
        self.assertIn("Knowledge Item", result.stdout)
        self.assertIn("Report Summary", result.stdout)
        self.assertIn("eu_ai_act", result.stdout)
        self.assertIn("2026-07-16_weekly_report_demo", result.stdout)


if __name__ == "__main__":
    unittest.main()
