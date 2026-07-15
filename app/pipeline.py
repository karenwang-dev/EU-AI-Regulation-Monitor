from app.crawler.service import crawl
from app.source.source_loader import load_monitors
from app.analysis.diff_processor import create_diff_result
from app.storage.service import (
    get_latest_snapshot,
    save_diff,
    save_snapshot,
)


def normalize_source(monitor: dict) -> dict:
    return {
        "source_id": monitor["id"],
        "name": monitor["name"],
        "url": monitor["url"],
        "keywords": monitor["keywords"],
        "category": monitor["category"],
        "frequency": monitor["frequency"],
    }


class MonitoringPipeline:

    def __init__(
        self,
        crawl_fn=crawl,
        save_snapshot_fn=save_snapshot,
        get_latest_snapshot_fn=get_latest_snapshot,
        create_diff_result_fn=create_diff_result,
        save_diff_fn=save_diff,
        load_sources_fn=load_monitors,
    ):
        self.crawl_fn = crawl_fn
        self.save_snapshot_fn = save_snapshot_fn
        self.get_latest_snapshot_fn = get_latest_snapshot_fn
        self.create_diff_result_fn = create_diff_result_fn
        self.save_diff_fn = save_diff_fn
        self.load_sources_fn = load_sources_fn

    def process_source(self, source: dict) -> dict:
        normalized = normalize_source(source)
        source_id = normalized["source_id"]

        try:
            previous_snapshot = self.get_latest_snapshot_fn(source_id)
            crawl_result = self.crawl_fn(normalized)
            snapshot = self.save_snapshot_fn(crawl_result)

            if previous_snapshot is None:
                return {
                    "source_id": source_id,
                    "name": normalized["name"],
                    "status": "first_snapshot",
                    "snapshot_id": snapshot["id"],
                    "diff_id": None,
                    "first_snapshot": True,
                    "message": "First snapshot captured; no diff available.",
                }

            if previous_snapshot["hash"] == snapshot["hash"]:
                return {
                    "source_id": source_id,
                    "name": normalized["name"],
                    "status": "skipped",
                    "snapshot_id": snapshot["id"],
                    "diff_id": None,
                    "first_snapshot": False,
                    "message": "Content unchanged; diff and AI analysis skipped.",
                }

            diff_result = self.create_diff_result_fn(
                source_id,
                previous_snapshot,
                snapshot,
            )

            if diff_result is None:
                return {
                    "source_id": source_id,
                    "name": normalized["name"],
                    "status": "skipped",
                    "snapshot_id": snapshot["id"],
                    "diff_id": None,
                    "first_snapshot": False,
                    "message": "Content unchanged; diff and AI analysis skipped.",
                }

            saved_diff = self.save_diff_fn(diff_result)

            return {
                "source_id": source_id,
                "name": normalized["name"],
                "status": "changed",
                "snapshot_id": snapshot["id"],
                "diff_id": saved_diff["id"],
                "first_snapshot": False,
                "message": "Content changed; diff stored.",
                "diff": {
                    "source_id": saved_diff["source_id"],
                    "old_snapshot_id": saved_diff["old_snapshot_id"],
                    "new_snapshot_id": saved_diff["new_snapshot_id"],
                    "changed": saved_diff["changed"],
                    "added_content": saved_diff["added_content"],
                    "removed_content": saved_diff["removed_content"],
                    "diff_text": saved_diff["diff_text"],
                },
            }

        except Exception as error:
            return {
                "source_id": source_id,
                "name": normalized.get("name", source_id),
                "status": "error",
                "snapshot_id": None,
                "diff_id": None,
                "first_snapshot": False,
                "message": str(error),
            }

    def run(self) -> list[dict]:
        sources = self.load_sources_fn()
        enabled_sources = [
            source
            for source in sources
            if source.get("enabled", True)
        ]

        results = []
        for source in enabled_sources:
            print(f"\nProcessing source: {source['name']} ({source['id']})")
            result = self.process_source(source)
            print(f"  Status: {result['status']} - {result['message']}")
            results.append(result)

        return results


def run_pipeline() -> list[dict]:
    return MonitoringPipeline().run()
