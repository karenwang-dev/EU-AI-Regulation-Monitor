from app.ai.analyzer import analyze_content
from app.ai.content_cleaner import clean_content
from app.crawler.service import crawl
from app.source.source_loader import load_monitors
from app.storage.service import (
    get_latest_snapshot,
    save_analysis,
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
        clean_content_fn=clean_content,
        analyze_content_fn=analyze_content,
        save_analysis_fn=save_analysis,
        load_sources_fn=load_monitors,
    ):
        self.crawl_fn = crawl_fn
        self.save_snapshot_fn = save_snapshot_fn
        self.get_latest_snapshot_fn = get_latest_snapshot_fn
        self.clean_content_fn = clean_content_fn
        self.analyze_content_fn = analyze_content_fn
        self.save_analysis_fn = save_analysis_fn
        self.load_sources_fn = load_sources_fn

    def process_source(self, source: dict) -> dict:
        normalized = normalize_source(source)
        source_id = normalized["source_id"]

        try:
            previous_snapshot = self.get_latest_snapshot_fn(source_id)
            crawl_result = self.crawl_fn(normalized)
            snapshot = self.save_snapshot_fn(crawl_result)

            if (
                previous_snapshot is not None
                and previous_snapshot["hash"] == snapshot["hash"]
            ):
                return {
                    "source_id": source_id,
                    "name": normalized["name"],
                    "status": "skipped",
                    "snapshot_id": snapshot["id"],
                    "analysis_id": None,
                    "message": "Content unchanged; AI analysis skipped.",
                }

            cleaned_content = self.clean_content_fn(
                crawl_result["markdown"]
            )
            analysis = self.analyze_content_fn(cleaned_content)
            analysis_record = self.save_analysis_fn(
                snapshot["id"],
                analysis,
            )

            return {
                "source_id": source_id,
                "name": normalized["name"],
                "status": "analyzed",
                "snapshot_id": snapshot["id"],
                "analysis_id": analysis_record["id"],
                "message": "Content changed; AI analysis completed.",
            }

        except Exception as error:
            return {
                "source_id": source_id,
                "name": normalized.get("name", source_id),
                "status": "error",
                "snapshot_id": None,
                "analysis_id": None,
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
