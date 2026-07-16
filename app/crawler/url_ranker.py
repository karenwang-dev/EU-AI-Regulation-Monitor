from __future__ import annotations

import re


NEGATIVE_TERMS = {
    "career",
    "contact",
    "cookie",
    "event",
    "job",
    "newsletter",
    "press",
    "privacy",
}

CATEGORY_TERM_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _keyword_in_text(keyword: str, text: str) -> bool:
    keyword_lower = keyword.lower().strip()
    text_lower = text.lower()
    if keyword_lower in text_lower:
        return True

    compact_keyword = re.sub(r"[^a-z0-9]+", "", keyword_lower)
    compact_text = re.sub(r"[^a-z0-9]+", "", text_lower)
    return bool(compact_keyword) and compact_keyword in compact_text


def _category_terms(category: str) -> list[str]:
    if not category:
        return []

    return [
        term.lower()
        for term in CATEGORY_TERM_PATTERN.findall(category)
        if term
    ]


def _score_link(link: dict, monitor: dict) -> dict:
    url = link.get("url", "")
    title = link.get("title", "")
    depth = link.get("depth", 0)

    url_lower = url.lower()
    title_lower = title.lower()
    combined = f"{url_lower} {title_lower}"

    score = 0
    reasons: list[str] = []

    for keyword in monitor.get("keywords", []):
        cleaned = keyword.strip()
        if not cleaned:
            continue

        if _keyword_in_text(cleaned, url):
            score += 30
            reasons.append(f"Keyword '{cleaned}' matched in URL (+30)")
        if _keyword_in_text(cleaned, title):
            score += 40
            reasons.append(f"Keyword '{cleaned}' matched in title (+40)")

    for term in _category_terms(monitor.get("category", "")):
        if term in url_lower or term in title_lower:
            score += 20
            reasons.append(f"Category term '{term}' matched (+20)")

    if depth == 0:
        score += 10
        reasons.append("Main page depth (+10)")

    if depth >= 2:
        score -= 10
        reasons.append("Deep page depth (-10)")

    if any(term in combined for term in NEGATIVE_TERMS):
        score -= 80
        reasons.append("Negative term detected (-80)")

    return {
        "url": url,
        "title": title,
        "depth": depth,
        "score": score,
        "reasons": reasons,
    }


def rank_urls(
    links: list[dict],
    monitor: dict,
) -> list[dict]:
    ranked = [_score_link(link, monitor) for link in links]
    ranked.sort(key=lambda item: (-item["score"], item["url"]))
    return ranked
