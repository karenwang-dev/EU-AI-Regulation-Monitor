import json

from app.ai.analyzer import client
from app.core.config import MODEL_NAME


EXTRACTION_MODE_FULL = "full"
EXTRACTION_MODE_DIFF = "diff"
VALID_EXTRACTION_MODES = {
    EXTRACTION_MODE_FULL,
    EXTRACTION_MODE_DIFF,
}


FULL_REGULATION_EXTRACTION_PROMPT = """
You are an EU regulatory compliance expert specializing in Smart TV
and consumer electronics products.

Extract structured regulation information from the FULL webpage content below.
Use ONLY information present in the content. Do not invent details.

Monitor metadata:
- Name: {monitor_name}
- Category: {monitor_category}
- URL: {monitor_url}
- Keywords: {monitor_keywords}

Rules:
1. Return ONLY valid JSON.
2. Do NOT use Markdown.
3. regulation_type must be one of:
   NEW, AMENDMENT, GUIDANCE, NEWS, OTHER
4. confidence must be one of: HIGH, MEDIUM, LOW
5. is_regulation_content must be true only when the page contains
   regulation, directive, standard, or compliance-related material.
6. Missing string values should be "".
7. Missing list values should be [].

Webpage content:

{content}

Return JSON in this format:
{{
  "title": "",
  "publish_date": "",
  "summary": "",
  "category": "",
  "regulation_type": "OTHER",
  "effective_date": "",
  "affected_countries": [],
  "affected_products": [],
  "affected_modules": [],
  "key_requirements": [],
  "actions_required": [],
  "is_regulation_content": false,
  "confidence": "LOW"
}}
"""


DIFF_REGULATION_EXTRACTION_PROMPT = """
You are an EU regulatory compliance expert specializing in Smart TV
and consumer electronics products.

Extract structured regulation information ONLY from the changed content below.
Do not assume information outside the diff.

Monitor metadata:
- Name: {monitor_name}
- Category: {monitor_category}
- URL: {monitor_url}
- Keywords: {monitor_keywords}

Rules:
1. Return ONLY valid JSON.
2. Do NOT use Markdown.
3. Base your extraction only on the changed content.
4. regulation_type must be one of:
   NEW, AMENDMENT, GUIDANCE, NEWS, OTHER
5. confidence must be one of: HIGH, MEDIUM, LOW
6. is_regulation_content must be true only when the changes relate to
   regulation, directive, standard, or compliance material.
7. Missing string values should be "".
8. Missing list values should be [].

Changed content:

ADDED CONTENT:
{added_content}

REMOVED CONTENT:
{removed_content}

DIFF:
{diff_text}

Return JSON in this format:
{{
  "title": "",
  "publish_date": "",
  "summary": "",
  "category": "",
  "regulation_type": "OTHER",
  "effective_date": "",
  "affected_countries": [],
  "affected_products": [],
  "affected_modules": [],
  "key_requirements": [],
  "actions_required": [],
  "is_regulation_content": false,
  "confidence": "LOW"
}}
"""


# Backward-compatible alias for Step 1 prompt name.
REGULATION_EXTRACTION_PROMPT = FULL_REGULATION_EXTRACTION_PROMPT


DEFAULT_EXTRACTION_RESULT = {
    "title": "",
    "publish_date": "",
    "summary": "",
    "category": "",
    "regulation_type": "OTHER",
    "effective_date": "",
    "affected_countries": [],
    "affected_products": [],
    "affected_modules": [],
    "key_requirements": [],
    "actions_required": [],
    "is_regulation_content": False,
    "confidence": "LOW",
}


def _normalize_string_list(values: list) -> list[str]:
    return [
        str(value).strip()
        for value in values
        if str(value).strip()
    ]


def _normalize_level(value: str, allowed: set[str], default: str) -> str:
    normalized = str(value).strip().upper()
    if normalized in allowed:
        return normalized
    return default


def _normalize_extraction_result(raw_result: dict) -> dict:
    return {
        "title": str(raw_result.get("title", "")).strip(),
        "publish_date": str(raw_result.get("publish_date", "")).strip(),
        "summary": str(raw_result.get("summary", "")).strip(),
        "category": str(raw_result.get("category", "")).strip(),
        "regulation_type": _normalize_level(
            raw_result.get("regulation_type", "OTHER"),
            {"NEW", "AMENDMENT", "GUIDANCE", "NEWS", "OTHER"},
            "OTHER",
        ),
        "effective_date": str(raw_result.get("effective_date", "")).strip(),
        "affected_countries": _normalize_string_list(
            raw_result.get("affected_countries", [])
        ),
        "affected_products": _normalize_string_list(
            raw_result.get("affected_products", [])
        ),
        "affected_modules": _normalize_string_list(
            raw_result.get("affected_modules", [])
        ),
        "key_requirements": _normalize_string_list(
            raw_result.get("key_requirements", [])
        ),
        "actions_required": _normalize_string_list(
            raw_result.get("actions_required", [])
        ),
        "is_regulation_content": bool(
            raw_result.get("is_regulation_content", False)
        ),
        "confidence": _normalize_level(
            raw_result.get("confidence", "LOW"),
            {"HIGH", "MEDIUM", "LOW"},
            "LOW",
        ),
    }


def _format_diff_section(lines: list[str]) -> str:
    if not lines:
        return "(none)"
    return "\n".join(lines)


def _build_full_prompt(content: str, monitor: dict) -> str:
    return FULL_REGULATION_EXTRACTION_PROMPT.format(
        monitor_name=monitor.get("name", ""),
        monitor_category=monitor.get("category", ""),
        monitor_url=monitor.get("url", ""),
        monitor_keywords=", ".join(monitor.get("keywords", [])),
        content=content or "(empty)",
    )


def _build_diff_prompt(diff_result: dict, monitor: dict) -> str:
    return DIFF_REGULATION_EXTRACTION_PROMPT.format(
        monitor_name=monitor.get("name", ""),
        monitor_category=monitor.get("category", ""),
        monitor_url=monitor.get("url", ""),
        monitor_keywords=", ".join(monitor.get("keywords", [])),
        added_content=_format_diff_section(
            diff_result.get("added_content", [])
        ),
        removed_content=_format_diff_section(
            diff_result.get("removed_content", [])
        ),
        diff_text=diff_result.get("diff_text", "") or "(none)",
    )


def _build_prompt(
    monitor: dict,
    *,
    mode: str,
    content: str = "",
    diff_result: dict | None = None,
) -> str:
    if mode == EXTRACTION_MODE_DIFF:
        if diff_result is None:
            raise ValueError(
                "diff_result is required when mode is 'diff'"
            )
        return _build_diff_prompt(diff_result, monitor)

    return _build_full_prompt(content, monitor)


def extract_regulation(
    content: str = "",
    monitor: dict | None = None,
    *,
    mode: str = EXTRACTION_MODE_FULL,
    diff_result: dict | None = None,
) -> dict:
    monitor_data = monitor or {}
    normalized_mode = str(mode).strip().lower()
    if normalized_mode not in VALID_EXTRACTION_MODES:
        raise ValueError(
            f"Unsupported extraction mode: {mode}. "
            f"Expected one of: {sorted(VALID_EXTRACTION_MODES)}"
        )

    prompt = _build_prompt(
        monitor_data,
        mode=normalized_mode,
        content=content,
        diff_result=diff_result,
    )

    response = client.responses.create(
        model=MODEL_NAME,
        input=prompt,
    )

    try:
        raw_result = json.loads(response.output_text)
        return _normalize_extraction_result(raw_result)
    except json.JSONDecodeError:
        print("AI regulation extraction returned invalid JSON.")
        print(response.output_text)
        return DEFAULT_EXTRACTION_RESULT.copy()
