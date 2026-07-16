from __future__ import annotations

import re
from difflib import SequenceMatcher


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _text_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(
        None,
        _normalize_text(left),
        _normalize_text(right),
    ).ratio()


def _list_similarity(left: list, right: list) -> float:
    left_values = {_normalize_text(item) for item in left if str(item).strip()}
    right_values = {
        _normalize_text(item) for item in right if str(item).strip()
    }
    if not left_values or not right_values:
        return 0.0
    intersection = left_values & right_values
    union = left_values | right_values
    return len(intersection) / len(union)


def _requirements_similarity(left: list, right: list) -> float:
    left_text = " ".join(str(item) for item in left if str(item).strip())
    right_text = " ".join(str(item) for item in right if str(item).strip())
    return _text_similarity(left_text, right_text)


def _build_similarity_reasons(
    title_score: float,
    summary_score: float,
    requirements_score: float,
    modules_score: float,
    shared_modules: set[str],
) -> list[str]:
    reasons: list[str] = []

    if shared_modules:
        reasons.append("same module")
    if requirements_score >= 0.5:
        reasons.append("similar requirement")
    if title_score >= 0.7:
        reasons.append("similar title")
    if summary_score >= 0.7:
        reasons.append("similar summary")

    if not reasons:
        reasons.append("overall text similarity")

    return reasons


def find_similar_knowledge(
    item: dict,
    existing_items: list[dict],
    threshold: float = 0.8,
) -> list[dict]:
    current_id = item.get("id")
    results: list[dict] = []

    item_modules = item.get("modules", [])
    item_requirements = item.get("requirements", [])

    for other in existing_items:
        other_id = other.get("id")
        if other_id is None or other_id == current_id:
            continue

        other_modules = other.get("modules", [])
        other_requirements = other.get("requirements", [])

        title_score = _text_similarity(
            item.get("title", ""),
            other.get("title", ""),
        )
        summary_score = _text_similarity(
            item.get("summary", ""),
            other.get("summary", ""),
        )
        requirements_score = _requirements_similarity(
            item_requirements,
            other_requirements,
        )
        modules_score = _list_similarity(item_modules, other_modules)

        similarity = round(
            (0.30 * title_score)
            + (0.25 * summary_score)
            + (0.25 * requirements_score)
            + (0.20 * modules_score),
            2,
        )

        if similarity < threshold:
            continue

        shared_modules = {
            _normalize_text(module)
            for module in item_modules
            if _normalize_text(module)
        } & {
            _normalize_text(module)
            for module in other_modules
            if _normalize_text(module)
        }

        results.append(
            {
                "id": other_id,
                "title": other.get("title", ""),
                "similarity": similarity,
                "reason": _build_similarity_reasons(
                    title_score,
                    summary_score,
                    requirements_score,
                    modules_score,
                    shared_modules,
                ),
            }
        )

    results.sort(key=lambda entry: entry["similarity"], reverse=True)
    return results
