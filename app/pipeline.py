from app.crawler.service import crawl
from app.crawler.url_resolver import resolve_monitor_urls
from app.source.source_loader import load_monitors
from app.analysis.diff_processor import create_diff_result
from app.ai.impact_analyzer import analyze_change_impact
from app.notification.notifier import notify_if_needed
from app.storage.service import (
    _get_service,
    get_latest_snapshot,
    save_analysis,
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


def _get_latest_snapshot_for_url(source_id: str, url: str) -> dict | None:
    service = _get_service()
    with service._connect() as connection:
        row = connection.execute(
            """
            SELECT * FROM snapshots
            WHERE source_id = ? AND url = ?
            ORDER BY timestamp DESC, id DESC
            LIMIT 1
            """,
            (source_id, url),
        ).fetchone()

    if row is None:
        return None

    return service._row_to_snapshot(row)


class MonitoringPipeline:

    def __init__(
        self,
        crawl_fn=crawl,
        save_snapshot_fn=save_snapshot,
        get_latest_snapshot_fn=get_latest_snapshot,
        get_latest_snapshot_for_url_fn=_get_latest_snapshot_for_url,
        create_diff_result_fn=create_diff_result,
        save_diff_fn=save_diff,
        analyze_change_impact_fn=analyze_change_impact,
        save_analysis_fn=save_analysis,
        notify_if_needed_fn=notify_if_needed,
        load_sources_fn=load_monitors,
        resolve_monitor_urls_fn=resolve_monitor_urls,
    ):
        self.crawl_fn = crawl_fn
        self.save_snapshot_fn = save_snapshot_fn
        self.get_latest_snapshot_fn = get_latest_snapshot_fn
        self.get_latest_snapshot_for_url_fn = get_latest_snapshot_for_url_fn
        self.create_diff_result_fn = create_diff_result_fn
        self.save_diff_fn = save_diff_fn
        self.analyze_change_impact_fn = analyze_change_impact_fn
        self.save_analysis_fn = save_analysis_fn
        self.notify_if_needed_fn = notify_if_needed_fn
        self.load_sources_fn = load_sources_fn
        self.resolve_monitor_urls_fn = resolve_monitor_urls_fn

    def _process_url(
        self,
        source: dict,
        normalized: dict,
        url_target: dict,
    ) -> dict:
        source_id = normalized["source_id"]
        target_url = url_target["url"]
        target_depth = url_target["depth"]

        crawl_source = {
            **normalized,
            "url": target_url,
            "name": url_target.get("title") or normalized["name"],
            "parent_monitor_id": source["id"],
            "discovered_depth": target_depth,
        }
        previous_snapshot = self.get_latest_snapshot_for_url_fn(
            source_id,
            target_url,
        )
        crawl_result = self.crawl_fn(crawl_source)
        crawl_result["parent_monitor_id"] = source["id"]
        crawl_result["discovered_depth"] = target_depth
        snapshot = self.save_snapshot_fn(crawl_result)

        base_result = {
            "url": target_url,
            "depth": target_depth,
            "snapshot_id": snapshot["id"],
            "parent_monitor_id": source["id"],
            "discovered_depth": target_depth,
        }

        if previous_snapshot is None:
            return {
                **base_result,
                "status": "first_snapshot",
                "diff_id": None,
                "analysis_id": None,
                "first_snapshot": True,
                "message": "First snapshot captured; no diff available.",
            }

        if previous_snapshot["hash"] == snapshot["hash"]:
            return {
                **base_result,
                "status": "skipped",
                "diff_id": None,
                "analysis_id": None,
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
                **base_result,
                "status": "skipped",
                "diff_id": None,
                "analysis_id": None,
                "first_snapshot": False,
                "message": "Content unchanged; diff and AI analysis skipped.",
            }

        saved_diff = self.save_diff_fn(diff_result)

        impact = self.analyze_change_impact_fn(saved_diff, source)
        impact["evidence"] = [
            {
                "source_id": source["id"],
                "name": source["name"],
                "url": target_url,
                "snapshot_id": snapshot["id"],
                "diff_id": saved_diff["id"],
                "timestamp": snapshot["timestamp"],
                "discovered_depth": target_depth,
            }
        ]
        analysis_record = self.save_analysis_fn(
            snapshot["id"],
            impact,
        )
        notification_result = self.notify_if_needed_fn(
            source,
            impact,
            snapshot["id"],
        )

        return {
            **base_result,
            "status": "analyzed",
            "diff_id": saved_diff["id"],
            "analysis_id": analysis_record["id"],
            "first_snapshot": False,
            "message": "Content changed; diff stored and impact analyzed.",
            "notification": notification_result,
            "diff": {
                "source_id": saved_diff["source_id"],
                "old_snapshot_id": saved_diff["old_snapshot_id"],
                "new_snapshot_id": saved_diff["new_snapshot_id"],
                "changed": saved_diff["changed"],
                "added_content": saved_diff["added_content"],
                "removed_content": saved_diff["removed_content"],
                "diff_text": saved_diff["diff_text"],
            },
            "impact": impact,
        }

    def _aggregate_url_results(
        self,
        normalized: dict,
        url_results: list[dict],
    ) -> dict:
        source_id = normalized["source_id"]

        if not url_results:
            return {
                "source_id": source_id,
                "name": normalized["name"],
                "status": "error",
                "snapshot_id": None,
                "diff_id": None,
                "analysis_id": None,
                "first_snapshot": False,
                "message": "No URLs were processed.",
            }

        if len(url_results) == 1:
            single = url_results[0]
            return {
                "source_id": source_id,
                "name": normalized["name"],
                "status": single["status"],
                "snapshot_id": single.get("snapshot_id"),
                "diff_id": single.get("diff_id"),
                "analysis_id": single.get("analysis_id"),
                "first_snapshot": single.get("first_snapshot", False),
                "message": single["message"],
                **{
                    key: value
                    for key, value in single.items()
                    if key
                    not in {
                        "status",
                        "snapshot_id",
                        "diff_id",
                        "analysis_id",
                        "first_snapshot",
                        "message",
                    }
                },
            }

        statuses = [result["status"] for result in url_results]
        if any(status == "analyzed" for status in statuses):
            overall_status = "analyzed"
        elif any(status == "error" for status in statuses):
            overall_status = "partial"
        elif all(status == "skipped" for status in statuses):
            overall_status = "skipped"
        elif all(status == "first_snapshot" for status in statuses):
            overall_status = "first_snapshot"
        else:
            overall_status = "partial"

        analyzed_results = [
            result for result in url_results if result["status"] == "analyzed"
        ]
        primary = analyzed_results[0] if analyzed_results else url_results[0]

        return {
            "source_id": source_id,
            "name": normalized["name"],
            "status": overall_status,
            "snapshot_id": primary.get("snapshot_id"),
            "diff_id": primary.get("diff_id"),
            "analysis_id": primary.get("analysis_id"),
            "first_snapshot": all(
                result.get("first_snapshot", False) for result in url_results
            ),
            "message": (
                f"Processed {len(url_results)} URL(s) for monitor "
                f"'{normalized['name']}'."
            ),
            "url_results": url_results,
            "pages_crawled": len(url_results),
        }

    def process_source(self, source: dict) -> dict:
        normalized = normalize_source(source)
        source_id = normalized["source_id"]

        try:
            url_targets = self.resolve_monitor_urls_fn(source)
            seen_urls: set[str] = set()
            url_results: list[dict] = []

            for url_target in url_targets:
                target_url = url_target["url"]
                if target_url in seen_urls:
                    continue
                seen_urls.add(target_url)

                try:
                    url_results.append(
                        self._process_url(source, normalized, url_target)
                    )
                except Exception as error:
                    url_results.append(
                        {
                            "url": target_url,
                            "depth": url_target.get("depth", 0),
                            "status": "error",
                            "snapshot_id": None,
                            "diff_id": None,
                            "analysis_id": None,
                            "first_snapshot": False,
                            "message": str(error),
                            "parent_monitor_id": source["id"],
                            "discovered_depth": url_target.get("depth", 0),
                        }
                    )

            return self._aggregate_url_results(normalized, url_results)

        except Exception as error:
            return {
                "source_id": source_id,
                "name": normalized.get("name", source_id),
                "status": "error",
                "snapshot_id": None,
                "diff_id": None,
                "analysis_id": None,
                "first_snapshot": False,
                "message": str(error),
            }

    def run(self, frequency: str | None = None) -> list[dict]:
        sources = self.load_sources_fn()
        enabled_sources = [
            source
            for source in sources
            if source.get("enabled", True)
        ]

        if frequency is not None:
            enabled_sources = [
                source
                for source in enabled_sources
                if source.get("frequency") == frequency
            ]

        results = []
        for source in enabled_sources:
            print(f"\nProcessing source: {source['name']} ({source['id']})")
            result = self.process_source(source)
            print(f"  Status: {result['status']} - {result['message']}")
            results.append(result)

        return results


def run_pipeline(frequency: str | None = None) -> list[dict]:
    return MonitoringPipeline().run(frequency=frequency)
