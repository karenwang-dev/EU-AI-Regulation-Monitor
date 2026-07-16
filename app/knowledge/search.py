from __future__ import annotations

import re
from typing import Callable

from app.storage.service import get_knowledge_item, get_knowledge_items

SCORE_TITLE = 100
SCORE_SUMMARY = 60
SCORE_REQUIREMENT = 40
SCORE_ACTION = 30
SCORE_MODULE = 80
SCORE_CATEGORY = 50
SCORE_NEWEST_BONUS = 5

CANDIDATE_POOL_LIMIT = 500


def _parse_keywords(query: str) -> list[str]:
    return [
        keyword
        for keyword in query.lower().split()
        if keyword.strip()
    ]


def _contains_keyword(value: str, keyword: str) -> bool:
    return keyword in value.lower()


def _load_candidate_items(
    *,
    category: str | None,
    module: str | None,
    get_items_fn: Callable,
    get_item_fn: Callable,
) -> list[dict]:
    listed_items = get_items_fn(
        category=category,
        module=module,
        limit=CANDIDATE_POOL_LIMIT,
    )

    candidates: list[dict] = []
    for listed_item in listed_items:
        item_id = listed_item.get("id")
        if item_id is None:
            continue
        full_item = get_item_fn(item_id)
        if full_item is not None:
            candidates.append(full_item)

    return candidates


def _score_item(
    item: dict,
    keywords: list[str],
    *,
    is_newest: bool,
) -> tuple[int, list[str]]:
    score = 0
    matched_fields: list[str] = []

    title = str(item.get("title", ""))
    summary = str(item.get("summary", ""))
    category = str(item.get("category", ""))
    requirements = item.get("requirements", [])
    actions = item.get("actions", [])
    modules = item.get("modules", [])

    for keyword in keywords:
        if _contains_keyword(title, keyword):
            score += SCORE_TITLE
            if "title" not in matched_fields:
                matched_fields.append("title")

        if _contains_keyword(summary, keyword):
            score += SCORE_SUMMARY
            if "summary" not in matched_fields:
                matched_fields.append("summary")

        for requirement in requirements:
            if _contains_keyword(str(requirement), keyword):
                score += SCORE_REQUIREMENT
                if "requirements" not in matched_fields:
                    matched_fields.append("requirements")
                break

        for action in actions:
            if _contains_keyword(str(action), keyword):
                score += SCORE_ACTION
                if "actions" not in matched_fields:
                    matched_fields.append("actions")
                break

        for module_name in modules:
            if _contains_keyword(str(module_name), keyword):
                score += SCORE_MODULE
                if "modules" not in matched_fields:
                    matched_fields.append("modules")
                break

        if _contains_keyword(category, keyword):
            score += SCORE_CATEGORY
            if "category" not in matched_fields:
                matched_fields.append("category")

    if is_newest:
        score += SCORE_NEWEST_BONUS

    return score, matched_fields


def _build_result_item(item: dict, score: int, matched_fields: list[str]) -> dict:
    return {
        "id": item["id"],
        "title": item.get("title", ""),
        "category": item.get("category", ""),
        "score": score,
        "matched_fields": matched_fields,
    }


def search_knowledge_items(
    query: str,
    *,
    category: str | None = None,
    module: str | None = None,
    limit: int = 20,
    get_items_fn: Callable | None = None,
    get_item_fn: Callable | None = None,
) -> list[dict]:
    items_fn = get_items_fn or get_knowledge_items
    item_fn = get_item_fn or get_knowledge_item

    candidates = _load_candidate_items(
        category=category,
        module=module,
        get_items_fn=items_fn,
        get_item_fn=item_fn,
    )

    keywords = _parse_keywords(query)

    if not keywords:
        return [
            _build_result_item(
                item,
                SCORE_NEWEST_BONUS if index == 0 else 0,
                [],
            )
            for index, item in enumerate(candidates[:limit])
        ]

    ranked_results: list[dict] = []
    for index, item in enumerate(candidates):
        score, matched_fields = _score_item(
            item,
            keywords,
            is_newest=(index == 0),
        )
        if score <= 0:
            continue
        ranked_results.append(
            _build_result_item(item, score, matched_fields)
        )

    ranked_results.sort(
        key=lambda result: (-result["score"], -result["id"])
    )
    return ranked_results[:limit]


def highlight_matches(text: str, keywords: list[str]) -> str:
    if not text or not keywords:
        return text

    highlighted = text
    unique_keywords = sorted(
        {keyword.strip() for keyword in keywords if keyword.strip()},
        key=len,
        reverse=True,
    )

    for keyword in unique_keywords:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        highlighted = pattern.sub(
            lambda match: f"<mark>{match.group(0)}</mark>",
            highlighted,
        )

    return highlighted
