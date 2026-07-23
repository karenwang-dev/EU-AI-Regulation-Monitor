from app.core.logging import get_logger
from app.crawler.service import crawl
from app.crawler.crawl_cache import should_crawl
from app.crawler.url_normalizer import normalize_page_url
from app.crawler.url_resolver import resolve_monitor_urls
from app.dev.change_test_site import LOCAL_TEST_MONITOR_ID
from app.monitoring.page_change_summary import (
    build_page_change_record,
    summarize_monitor_run,
)
from app.monitors.repository import get_monitor_repository
from app.source.source_loader import load_monitors
from app.analysis.diff_processor import create_diff_result
from app.ai.impact_analyzer import analyze_change_impact
from app.ai.regulation_extractor import (
    EXTRACTION_MODE_DIFF,
    extract_regulation,
)
from app.knowledge.builder import build_knowledge_item
from app.knowledge.statistics import fetch_all_knowledge_items
from app.notification.notifier import notify_if_needed
from app.storage.service import (
    _get_service,
    get_crawl_cache,
    get_latest_snapshot,
    get_snapshot_by_id,
    save_analysis,
    save_diff,
    save_knowledge_item,
    save_snapshot,
    update_crawl_cache,
)

logger = get_logger(__name__)


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
    normalized_target = normalize_page_url(url)
    with service._connect() as connection:
        rows = connection.execute(
            """
            SELECT * FROM snapshots
            WHERE source_id = ?
            ORDER BY timestamp DESC, id DESC
            """,
            (source_id,),
        ).fetchall()

    for row in rows:
        snapshot = service._row_to_snapshot(row)
        if normalize_page_url(snapshot.get("url", "")) == normalized_target:
            return snapshot

    return None


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
        extract_regulation_fn=extract_regulation,
        save_analysis_fn=save_analysis,
        build_knowledge_item_fn=build_knowledge_item,
        fetch_all_knowledge_items_fn=None,
        save_knowledge_item_fn=save_knowledge_item,
        notify_if_needed_fn=notify_if_needed,
        load_sources_fn=load_monitors,
        resolve_monitor_urls_fn=resolve_monitor_urls,
        should_crawl_fn=should_crawl,
        get_crawl_cache_fn=get_crawl_cache,
        update_crawl_cache_fn=update_crawl_cache,
        get_snapshot_by_id_fn=get_snapshot_by_id,
        get_distinct_monitor_urls_fn=None,
    ):
        self.crawl_fn = crawl_fn
        self.save_snapshot_fn = save_snapshot_fn
        self.get_latest_snapshot_fn = get_latest_snapshot_fn
        self.get_latest_snapshot_for_url_fn = get_latest_snapshot_for_url_fn
        self.create_diff_result_fn = create_diff_result_fn
        self.save_diff_fn = save_diff_fn
        self.analyze_change_impact_fn = analyze_change_impact_fn
        self.extract_regulation_fn = extract_regulation_fn
        self.save_analysis_fn = save_analysis_fn
        self.build_knowledge_item_fn = build_knowledge_item_fn
        if fetch_all_knowledge_items_fn is None:
            fetch_all_knowledge_items_fn = lambda: fetch_all_knowledge_items(
                _get_service()
            )
        self.fetch_all_knowledge_items_fn = fetch_all_knowledge_items_fn
        self.save_knowledge_item_fn = save_knowledge_item_fn
        self.notify_if_needed_fn = notify_if_needed_fn
        self.load_sources_fn = load_sources_fn
        self.resolve_monitor_urls_fn = resolve_monitor_urls_fn
        self.should_crawl_fn = should_crawl_fn
        self.get_crawl_cache_fn = get_crawl_cache_fn
        self.update_crawl_cache_fn = update_crawl_cache_fn
        self.get_snapshot_by_id_fn = get_snapshot_by_id_fn
        if get_distinct_monitor_urls_fn is None:
            from app.storage.service import _get_service

            get_distinct_monitor_urls_fn = (
                lambda source_id: _get_service().get_distinct_monitor_urls(source_id)
            )
        self.get_distinct_monitor_urls_fn = get_distinct_monitor_urls_fn

    def _should_bypass_crawl_cache(self, source: dict) -> bool:
        if source.get("id") == LOCAL_TEST_MONITOR_ID:
            return True
        if source.get("skip_ai_analysis"):
            return True
        monitor_url = str(source.get("url", "")).lower()
        if source.get("fetch_mode") == "http" and (
            "127.0.0.1" in monitor_url or "localhost" in monitor_url
        ):
            return True
        return False

    def _apply_page_summary_to_aggregate(
        self,
        aggregated: dict,
        url_results: list[dict],
        summary: dict,
    ) -> dict:
        pages_changed = int(summary.get("pages_changed", 0))
        aggregated["page_change_summary"] = summary
        aggregated["pages_changed"] = pages_changed
        aggregated["homepage_changed"] = summary.get("homepage_changed", False)
        aggregated["child_pages_changed"] = summary.get("child_pages_changed", 0)

        if pages_changed <= 0:
            return aggregated

        changed_results = [
            result
            for result in url_results
            if result.get("status") in {"analyzed", "changed"}
        ]
        if not changed_results:
            return aggregated

        primary = changed_results[0]
        aggregated["status"] = (
            "analyzed"
            if any(result.get("status") == "analyzed" for result in changed_results)
            else "changed"
        )
        aggregated["diff_id"] = primary.get("diff_id")
        aggregated["analysis_id"] = primary.get("analysis_id")
        aggregated["snapshot_id"] = primary.get("snapshot_id")
        return aggregated

    def _log_monitor_run(
        self,
        source: dict,
        url_targets: list[dict],
        url_results: list[dict],
        summary: dict,
    ) -> None:
        logger.info(
            "Monitor run details: monitor_id=%s enabled=%s config_source=%s "
            "crawl_mode=%s skip_ai_analysis=%s",
            source.get("id"),
            source.get("enabled"),
            get_monitor_repository().db_path.resolve(),
            source.get("crawl_mode"),
            source.get("skip_ai_analysis", False),
        )
        logger.info(
            "Pages discovered=%s normalized_urls=%s",
            len(url_targets),
            [normalize_page_url(item["url"]) for item in url_targets],
        )
        logger.info(
            "Crawl cache bypass=%s for monitor_id=%s",
            self._should_bypass_crawl_cache(source),
            source.get("id"),
        )
        for result in url_results:
            page_change = result.get("page_change") or {}
            logger.info(
                "Page result: url=%s normalized_url=%s status=%s page_changed=%s "
                "previous_snapshot_found=%s previous_snapshot_id=%s snapshot_id=%s "
                "previous_hash=%s after_hash=%s page_type=%s change_kind=%s "
                "diff_id=%s analysis_id=%s cache_hit=%s",
                result.get("url"),
                normalize_page_url(result.get("url", "")),
                result.get("status"),
                result.get("page_changed"),
                result.get("previous_snapshot_found"),
                result.get("previous_snapshot_id"),
                result.get("snapshot_id"),
                result.get("previous_hash") or page_change.get("before_hash"),
                result.get("content_hash") or page_change.get("after_hash"),
                page_change.get("page_type"),
                page_change.get("change_kind"),
                result.get("diff_id"),
                result.get("analysis_id"),
                result.get("cache_hit"),
            )
        logger.info("Page change summary: %s", summary)

    def _fetch_snapshot_for_url(
        self,
        source: dict,
        normalized: dict,
        url_target: dict,
    ) -> tuple[dict, bool]:
        target_url = url_target["url"]
        frequency = source.get("frequency", normalized["frequency"])

        if (
            not self._should_bypass_crawl_cache(source)
            and not self.should_crawl_fn(target_url, frequency)
        ):
            cache_entry = self.get_crawl_cache_fn(target_url)
            if cache_entry is not None:
                cached_snapshot = self.get_snapshot_by_id_fn(
                    cache_entry["last_snapshot_id"]
                )
                if cached_snapshot is not None:
                    logger.info(
                        "Crawl cache hit for %s -> snapshot_id=%s hash=%s",
                        target_url,
                        cached_snapshot.get("id"),
                        cached_snapshot.get("hash"),
                    )
                    return cached_snapshot, True

        logger.info("Fetching fresh content for %s", target_url)
        crawl_source = {
            **normalized,
            "url": target_url,
            "name": url_target.get("title") or normalized["name"],
            "parent_monitor_id": source["id"],
            "discovered_depth": url_target["depth"],
            "parent_url": source.get("url") if url_target["depth"] else None,
            "monitor": source,
        }
        crawl_result = self.crawl_fn(crawl_source)
        crawl_result["parent_monitor_id"] = source["id"]
        crawl_result["discovered_depth"] = url_target["depth"]
        snapshot = self.save_snapshot_fn(crawl_result)
        self.update_crawl_cache_fn(
            target_url,
            snapshot["id"],
            snapshot["hash"],
        )
        return snapshot, False

    def _process_url(
        self,
        source: dict,
        normalized: dict,
        url_target: dict,
    ) -> dict:
        source_id = normalized["source_id"]
        target_url = url_target["url"]
        target_depth = url_target["depth"]

        previous_snapshot = self.get_latest_snapshot_for_url_fn(
            source_id,
            target_url,
        )
        snapshot, cache_hit = self._fetch_snapshot_for_url(
            source,
            normalized,
            url_target,
        )

        base_result = {
            "url": target_url,
            "depth": target_depth,
            "snapshot_id": snapshot["id"],
            "parent_monitor_id": source["id"],
            "discovered_depth": target_depth,
            "cache_hit": cache_hit,
            "content_hash": snapshot.get("hash"),
            "previous_hash": previous_snapshot.get("hash") if previous_snapshot else None,
            "previous_snapshot_found": previous_snapshot is not None,
            "previous_snapshot_id": (
                previous_snapshot.get("id") if previous_snapshot else None
            ),
        }

        def _with_page_changed(result: dict) -> dict:
            return {
                **result,
                "page_changed": result.get("status") in {"analyzed", "changed"},
            }

        if cache_hit:
            base_result["message_prefix"] = "Crawl cache hit;"
        else:
            base_result["message_prefix"] = ""

        if previous_snapshot is None:
            return _with_page_changed(
                {
                    **base_result,
                    "status": "first_snapshot",
                    "diff_id": None,
                    "analysis_id": None,
                    "first_snapshot": True,
                    "message": (
                        f"{base_result['message_prefix']} First snapshot captured; "
                        "no diff available."
                    ).strip(),
                }
            )

        if previous_snapshot["hash"] == snapshot["hash"]:
            return _with_page_changed(
                {
                    **base_result,
                    "status": "skipped",
                    "diff_id": None,
                    "analysis_id": None,
                    "first_snapshot": False,
                    "message": (
                        f"{base_result['message_prefix']} Content unchanged; "
                        "diff and AI analysis skipped."
                    ).strip(),
                }
            )

        diff_result = self.create_diff_result_fn(
            source_id,
            previous_snapshot,
            snapshot,
        )

        if diff_result is None:
            return _with_page_changed(
                {
                    **base_result,
                    "status": "skipped",
                    "diff_id": None,
                    "analysis_id": None,
                    "first_snapshot": False,
                    "message": (
                        f"{base_result['message_prefix']} Content unchanged; "
                        "diff and AI analysis skipped."
                    ).strip(),
                }
            )

        saved_diff = self.save_diff_fn(diff_result)

        page_change = build_page_change_record(
            monitor=source,
            page_url=target_url,
            page_title=snapshot.get("title", target_url),
            before_hash=previous_snapshot.get("hash"),
            after_hash=snapshot.get("hash"),
            diff_text=saved_diff.get("diff_text", ""),
            change_kind="page_changed",
            parent_url=source.get("url"),
            crawl_depth=target_depth,
        )

        if source.get("skip_ai_analysis"):
            impact = {
                "impact_level": "UNASSESSED",
                "analysis_skipped": True,
                "affected_modules": [],
                "reason": "Change detected for test monitor (AI analysis skipped).",
                "recommended_actions": [],
                "confidence": "NONE",
                "page_change": page_change,
                "evidence": [
                    {
                        "source_id": source["id"],
                        "name": source["name"],
                        "url": target_url,
                        "snapshot_id": snapshot["id"],
                        "diff_id": saved_diff["id"],
                        "timestamp": snapshot["timestamp"],
                        "discovered_depth": target_depth,
                        "page_type": page_change["page_type"],
                        "change_kind": page_change["change_kind"],
                    }
                ],
            }
            analysis_record = self.save_analysis_fn(
                snapshot["id"],
                impact,
            )
            return _with_page_changed(
                {
                    **base_result,
                    "status": "changed",
                    "diff_id": saved_diff["id"],
                    "analysis_id": analysis_record["id"],
                    "first_snapshot": False,
                    "page_change": page_change,
                    "message": (
                        f"{base_result['message_prefix']} Content changed; "
                        "diff stored (AI analysis skipped)."
                    ).strip(),
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
            )

        regulation_extraction = self.extract_regulation_fn(
            monitor=source,
            mode=EXTRACTION_MODE_DIFF,
            diff_result=saved_diff,
        )
        impact = self.analyze_change_impact_fn(saved_diff, source)
        impact["regulation_extraction"] = regulation_extraction
        page_change = build_page_change_record(
            monitor=source,
            page_url=target_url,
            page_title=snapshot.get("title", target_url),
            before_hash=previous_snapshot.get("hash"),
            after_hash=snapshot.get("hash"),
            diff_text=saved_diff.get("diff_text", ""),
            change_kind="page_changed",
            parent_url=source.get("url"),
            crawl_depth=target_depth,
        )
        impact["page_change"] = page_change
        impact["evidence"] = [
            {
                "source_id": source["id"],
                "name": source["name"],
                "url": target_url,
                "snapshot_id": snapshot["id"],
                "diff_id": saved_diff["id"],
                "timestamp": snapshot["timestamp"],
                "discovered_depth": target_depth,
                "page_type": page_change["page_type"],
                "change_kind": page_change["change_kind"],
            }
        ]
        analysis_record = self.save_analysis_fn(
            snapshot["id"],
            impact,
        )

        knowledge_id = None
        try:
            existing_items = self.fetch_all_knowledge_items_fn()
            knowledge_item = self.build_knowledge_item_fn(
                snapshot,
                source,
                impact,
                existing_items,
            )
            if knowledge_item:
                saved_knowledge = self.save_knowledge_item_fn(
                    knowledge_item
                )
                knowledge_id = saved_knowledge["id"]
        except Exception:
            knowledge_id = None

        notification_result = self.notify_if_needed_fn(
            source,
            impact,
            snapshot["id"],
        )

        return _with_page_changed(
            {
                **base_result,
                "status": "analyzed",
                "diff_id": saved_diff["id"],
                "analysis_id": analysis_record["id"],
                "knowledge_id": knowledge_id,
                "first_snapshot": False,
                "page_change": page_change,
                "message": (
                    f"{base_result['message_prefix']} Content changed; "
                    "diff stored and impact analyzed."
                ).strip(),
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
                "regulation_extraction": regulation_extraction,
            }
        )

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
        if any(status in {"analyzed", "changed"} for status in statuses):
            overall_status = "analyzed" if any(
                status == "analyzed" for status in statuses
            ) else "changed"
        elif any(status == "error" for status in statuses):
            overall_status = "partial"
        elif all(status == "skipped" for status in statuses):
            overall_status = "skipped"
        elif all(status == "first_snapshot" for status in statuses):
            overall_status = "first_snapshot"
        else:
            overall_status = "partial"

        analyzed_results = [
            result
            for result in url_results
            if result.get("status") in {"analyzed", "changed"}
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
            discovery_summary: dict | None = None
            if source.get("id") == LOCAL_TEST_MONITOR_ID:
                from app.dev.change_test_site import build_local_test_monitor_urls

                url_targets = build_local_test_monitor_urls(source["url"], source)
            else:
                resolve_result = self.resolve_monitor_urls_fn(source)
                if hasattr(resolve_result, "urls"):
                    url_targets = resolve_result.urls
                    discovery_summary = resolve_result.discovery_summary
                else:
                    url_targets = resolve_result

            previous_urls = self.get_distinct_monitor_urls_fn(source_id)
            normalized_previous = {normalize_page_url(url) for url in previous_urls}
            seen_urls: set[str] = set()
            url_results: list[dict] = []

            for url_target in url_targets:
                target_url = url_target["url"]
                normalized_target = normalize_page_url(target_url)
                if normalized_target in seen_urls:
                    continue
                seen_urls.add(normalized_target)

                try:
                    url_result = self._process_url(source, normalized, url_target)
                    if (
                        normalized_previous
                        and url_result.get("status") == "first_snapshot"
                        and normalized_target not in normalized_previous
                    ):
                        url_result = {
                            **url_result,
                            "status": "page_added",
                            "message": "New page discovered.",
                        }
                    url_results.append(url_result)
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

            current_urls = {normalize_page_url(item["url"]) for item in url_targets}
            if normalized_previous:
                added = {
                    normalize_page_url(url)
                    for url in current_urls - normalized_previous
                }
                removed = {
                    normalize_page_url(url)
                    for url in normalized_previous - current_urls
                }
                for url in sorted(added):
                    if not any(
                        normalize_page_url(result.get("url", "")) == url
                        for result in url_results
                    ):
                        url_results.append(
                            {
                                "url": url,
                                "depth": 1,
                                "status": "page_added",
                                "snapshot_id": None,
                                "diff_id": None,
                                "analysis_id": None,
                                "first_snapshot": True,
                                "message": "New page discovered.",
                                "parent_monitor_id": source["id"],
                                "discovered_depth": 1,
                            }
                        )
                for url in sorted(removed):
                    url_results.append(
                        {
                            "url": url,
                            "depth": 1,
                            "status": "page_removed",
                            "snapshot_id": None,
                            "diff_id": None,
                            "analysis_id": None,
                            "first_snapshot": False,
                            "message": "Previously monitored page no longer discovered.",
                            "parent_monitor_id": source["id"],
                            "discovered_depth": 1,
                        }
                    )

            aggregated = self._aggregate_url_results(normalized, url_results)
            summary = summarize_monitor_run(
                source,
                url_results,
                previous_urls=normalized_previous if previous_urls else set(),
                current_urls=current_urls,
            )
            aggregated = self._apply_page_summary_to_aggregate(
                aggregated,
                url_results,
                summary,
            )
            if discovery_summary is not None:
                aggregated["discovery_summary"] = discovery_summary
            self._log_monitor_run(
                source,
                url_targets,
                url_results,
                summary,
            )
            return aggregated

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

        logger.info(
            "Pipeline run started for %s enabled source(s)",
            len(enabled_sources),
        )

        results = []
        for source in enabled_sources:
            logger.info(
                "Processing source: %s (%s)",
                source["name"],
                source["id"],
            )
            result = self.process_source(source)
            logger.info(
                "Source %s status: %s - %s",
                source["id"],
                result["status"],
                result["message"],
            )
            results.append(result)

        return results


def run_pipeline(frequency: str | None = None) -> list[dict]:
    return MonitoringPipeline().run(frequency=frequency)
