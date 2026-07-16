import unittest

from app.web.source_helper import (
    build_evidence_fallback,
    build_source_tree,
    enrich_changes_with_source_metadata,
    format_depth_label,
    normalize_source_node,
)


class TestSourceHelper(unittest.TestCase):

    def _monitor(self) -> dict:
        return {
            "id": "ec",
            "name": "European Commission",
            "url": "https://example.com/ec",
        }

    def test_format_depth_label(self):
        self.assertEqual(format_depth_label(0), "Main Page")
        self.assertEqual(format_depth_label(None), "Main Page")
        self.assertEqual(format_depth_label(1), "Discovered Page")
        self.assertEqual(format_depth_label(2), "Discovered Page")

    def test_build_source_tree_renders_multiple_sources(self):
        monitor = self._monitor()
        evidence = [
            {
                "source_id": "ec",
                "parent_monitor_id": "ec",
                "name": "European Commission",
                "url": "https://example.com/ec",
                "snapshot_id": 1,
                "diff_id": 10,
                "timestamp": "2026-07-15T10:00:00",
                "discovered_depth": 0,
            },
            {
                "source_id": "ec",
                "parent_monitor_id": "ec",
                "name": "AI Act Policy",
                "url": "https://example.com/ec/ai-act",
                "snapshot_id": 2,
                "diff_id": 11,
                "timestamp": "2026-07-15T11:00:00",
                "discovered_depth": 1,
            },
        ]

        tree = build_source_tree(evidence, monitor, monitor_map={"ec": monitor})

        self.assertEqual(len(tree), 2)
        self.assertEqual(tree[0]["depth_label"], "Main Page")
        self.assertEqual(tree[1]["depth_label"], "Discovered Page")
        self.assertEqual(tree[1]["title"], "AI Act Policy")
        self.assertEqual(tree[1]["parent_monitor_name"], "European Commission")

    def test_build_source_tree_legacy_fallback_without_evidence(self):
        monitor = self._monitor()
        diff = {
            "id": 5,
            "source_id": "ec",
            "new_snapshot_id": 9,
            "created_at": "2026-07-15T12:00:00",
        }
        snapshot = {
            "id": 9,
            "url": "https://example.com/ec",
        }

        tree = build_source_tree(None, monitor, diff=diff, snapshot=snapshot)

        self.assertEqual(len(tree), 1)
        self.assertEqual(tree[0]["url"], "https://example.com/ec")
        self.assertEqual(tree[0]["depth_label"], "Main Page")
        self.assertEqual(tree[0]["parent_monitor_name"], "European Commission")
        self.assertEqual(tree[0]["snapshot_id"], 9)
        self.assertEqual(tree[0]["diff_id"], 5)

    def test_normalize_source_node_infers_depth_for_legacy_evidence(self):
        monitor = self._monitor()
        node = normalize_source_node(
            {
                "source_id": "ec",
                "name": "AI Act Policy",
                "url": "https://example.com/ec/ai-act",
                "snapshot_id": 2,
                "diff_id": 11,
                "timestamp": "2026-07-15T11:00:00",
            },
            monitor,
            monitor_map={"ec": monitor},
        )

        self.assertEqual(node["discovered_depth"], 1)
        self.assertEqual(node["depth_label"], "Discovered Page")
        self.assertEqual(node["parent_monitor_id"], "ec")

    def test_enrich_changes_with_source_metadata(self):
        changes = [
            {
                "source_id": "ec",
                "source_url": "https://example.com/ec",
                "diff_id": 1,
            },
            {
                "source_id": "ec",
                "source_url": "https://example.com/ec/ai-act",
                "diff_id": 2,
            },
        ]

        enriched = enrich_changes_with_source_metadata(changes)

        self.assertEqual(enriched[0]["changed_pages_count"], 2)
        self.assertEqual(len(enriched[0]["source_urls"]), 2)
        self.assertEqual(enriched[1]["changed_pages_count"], 2)

    def test_build_evidence_fallback_uses_snapshot_url(self):
        monitor = self._monitor()
        diff = {"id": 3, "source_id": "ec", "new_snapshot_id": 4}
        snapshot = {"url": "https://example.com/ec/page"}

        fallback = build_evidence_fallback(diff, monitor, snapshot)

        self.assertEqual(fallback[0]["url"], "https://example.com/ec/page")


if __name__ == "__main__":
    unittest.main()
