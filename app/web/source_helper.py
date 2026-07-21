from __future__ import annotations


def format_depth_label(discovered_depth: int | None) -> str:
    if discovered_depth is None or discovered_depth == 0:
        return "Main Page"
    return "Discovered Page"


def format_page_type_label(page_type: str | None) -> str:
    if not page_type:
        return ""
    return str(page_type).strip()


def extract_page_type_from_evidence(
    analysis: dict | None,
    snapshot: dict | None,
    monitor: dict,
) -> str:
    if analysis:
        page_change = analysis.get("page_change")
        if isinstance(page_change, dict) and page_change.get("page_type"):
            return str(page_change["page_type"])

        evidence = analysis.get("evidence", [])
        if evidence:
            page_type = evidence[0].get("page_type")
            if page_type:
                return str(page_type)

            change_kind = evidence[0].get("change_kind")
            if change_kind == "page_added":
                return "Added page"
            if change_kind == "page_removed":
                return "Removed page"

            source_url = evidence[0].get("url", "")
            monitor_url = monitor.get("url", "")
            if source_url and monitor_url:
                from app.crawler.url_normalizer import normalize_page_url

                if normalize_page_url(source_url) == normalize_page_url(monitor_url):
                    return "Homepage"
                if source_url:
                    return "Child page"

    if snapshot:
        snapshot_url = snapshot.get("url", "")
        monitor_url = monitor.get("url", "")
        if snapshot_url and monitor_url:
            from app.crawler.url_normalizer import normalize_page_url

            if normalize_page_url(snapshot_url) == normalize_page_url(monitor_url):
                return "Homepage"
            return "Child page"

    return ""


def build_evidence_fallback(
    diff: dict,
    monitor: dict,
    snapshot: dict | None = None,
) -> list[dict]:
    url = snapshot.get("url", "") if snapshot else ""
    if not url:
        url = monitor.get("url", "")

    return [
        {
            "source_id": diff.get("source_id", monitor.get("id", "")),
            "name": monitor.get("name", diff.get("source_id", "Unknown")),
            "url": url,
            "snapshot_id": diff.get("new_snapshot_id"),
            "diff_id": diff.get("id"),
            "timestamp": diff.get("created_at", ""),
        }
    ]


def normalize_source_node(
    item: dict,
    monitor: dict,
    monitor_map: dict[str, dict] | None = None,
) -> dict:
    monitor_map = monitor_map or {}
    parent_id = (
        item.get("parent_monitor_id")
        or item.get("source_id")
        or monitor.get("id", "")
    )

    parent_monitor = monitor_map.get(parent_id, {})
    if not parent_monitor and parent_id == monitor.get("id"):
        parent_monitor = monitor

    discovered_depth = item.get("discovered_depth")
    if discovered_depth is None:
        monitor_url = monitor.get("url", "")
        discovered_depth = 0 if item.get("url", "") == monitor_url else 1

    title = item.get("name") or item.get("title") or item.get("url", "Unknown")

    return {
        "title": title,
        "name": title,
        "url": item.get("url", ""),
        "parent_monitor_id": parent_id,
        "parent_monitor_name": parent_monitor.get("name", parent_id),
        "discovered_depth": discovered_depth,
        "depth_label": format_depth_label(discovered_depth),
        "snapshot_id": item.get("snapshot_id"),
        "diff_id": item.get("diff_id"),
        "timestamp": item.get("timestamp", ""),
    }


def build_source_tree(
    evidence: list[dict] | None,
    monitor: dict,
    diff: dict | None = None,
    monitor_map: dict[str, dict] | None = None,
    snapshot: dict | None = None,
) -> list[dict]:
    if evidence:
        items = evidence
    else:
        items = build_evidence_fallback(diff or {}, monitor, snapshot)

    tree = [
        normalize_source_node(item, monitor, monitor_map=monitor_map)
        for item in items
    ]
    return sorted(tree, key=lambda node: (node["discovered_depth"], node["url"]))


def enrich_changes_with_source_metadata(changes: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for change in changes:
        grouped.setdefault(change["source_id"], []).append(change)

    enriched: list[dict] = []
    for change in changes:
        monitor_changes = grouped[change["source_id"]]
        source_urls: list[str] = []
        seen_urls: set[str] = set()

        for item in monitor_changes:
            url = item.get("source_url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                source_urls.append(url)

        enriched.append(
            {
                **change,
                "changed_pages_count": len(monitor_changes),
                "source_urls": source_urls,
            }
        )

    return enriched


def extract_source_url_from_evidence(
    analysis: dict | None,
    snapshot: dict | None,
    monitor: dict,
) -> str:
    if analysis:
        evidence = analysis.get("evidence", [])
        if evidence:
            return evidence[0].get("url", "")

    if snapshot:
        return snapshot.get("url", "")

    return monitor.get("url", "")


def extract_discovered_depth_from_evidence(
    analysis: dict | None,
    snapshot: dict | None,
    monitor: dict,
) -> int | None:
    if not analysis:
        return None

    evidence = analysis.get("evidence", [])
    if not evidence:
        return None

    depth = evidence[0].get("discovered_depth")
    if depth is not None:
        return depth

    source_url = evidence[0].get("url", "")
    if source_url and source_url == monitor.get("url", ""):
        return 0

    return None


def extract_analysis_skipped_from_evidence(analysis: dict | None) -> bool:
    if not analysis:
        return False
    if analysis.get("analysis_skipped"):
        return True
    return str(analysis.get("impact_level", "")).strip().upper() == "UNASSESSED"


def extract_change_kind_from_evidence(analysis: dict | None) -> str:
    if not analysis:
        return ""

    page_change = analysis.get("page_change")
    if isinstance(page_change, dict) and page_change.get("change_kind"):
        return str(page_change["change_kind"])

    evidence = analysis.get("evidence", [])
    if evidence and evidence[0].get("change_kind"):
        return str(evidence[0]["change_kind"])

    return "page_changed"
