from __future__ import annotations

import json
from datetime import datetime

from app.ai.analyzer import client as default_client
from app.core.config import MODEL_NAME

REPORT_GENERATION_PROMPT = """
You are an EU regulatory compliance expert specializing in Smart TV
and consumer electronics products.

Generate a weekly compliance monitoring report using ONLY the structured
report data below.

Rules:
1. Return ONLY valid JSON.
2. Do NOT use Markdown.
3. Do NOT invent regulations, webpage content, or facts not present
   in the report data.
4. Focus on Smart TV product impact across hardware and software modules
   such as Network, OTA update, AI features, DRM, cybersecurity controls,
   and accessibility features.
5. Highlight HIGH and MEDIUM risk changes prominently.
6. Provide concise, actionable recommendations for compliance teams.
7. impact_level in key_changes must be one of: HIGH, MEDIUM, LOW, NONE
8. If there are no changes, return empty strings/lists appropriately.

Report period:
- Start: {period_start}
- End: {period_end}

Report summary:
{report_summary_json}

Report changes:
{report_changes_json}

Return JSON in this format:
{{
  "executive_summary": "",
  "key_changes": [
    {{
      "title": "",
      "summary": "",
      "impact_level": "HIGH",
      "affected_modules": [],
      "recommended_actions": []
    }}
  ],
  "risk_summary": ""
}}
"""

REPORT_TITLE = "Weekly Regulation Monitoring Report"
VALID_IMPACT_LEVELS = {"HIGH", "MEDIUM", "LOW", "NONE"}

DEFAULT_AI_REPORT_CONTENT = {
    "executive_summary": "",
    "key_changes": [],
    "risk_summary": "",
}


def _normalize_impact_level(value) -> str:
    normalized = str(value or "NONE").strip().upper()
    if normalized in VALID_IMPACT_LEVELS:
        return normalized
    return "NONE"


def _normalize_string_list(values) -> list[str]:
    if not values:
        return []
    return [
        str(value).strip()
        for value in values
        if str(value).strip()
    ]


def _normalize_key_change(raw_change: dict) -> dict:
    return {
        "title": str(raw_change.get("title", "")).strip(),
        "summary": str(raw_change.get("summary", "")).strip(),
        "impact_level": _normalize_impact_level(
            raw_change.get("impact_level")
        ),
        "affected_modules": _normalize_string_list(
            raw_change.get("affected_modules")
        ),
        "recommended_actions": _normalize_string_list(
            raw_change.get("recommended_actions")
        ),
    }


def _normalize_ai_report_content(raw_result: dict) -> dict:
    key_changes = raw_result.get("key_changes", [])
    if not isinstance(key_changes, list):
        key_changes = []

    normalized_changes = [
        _normalize_key_change(change)
        for change in key_changes
        if isinstance(change, dict)
    ]

    return {
        "executive_summary": str(
            raw_result.get("executive_summary", "")
        ).strip(),
        "key_changes": normalized_changes,
        "risk_summary": str(raw_result.get("risk_summary", "")).strip(),
    }


def _build_prompt(report_data: dict) -> str:
    period = report_data.get("period") or {}
    summary = report_data.get("summary") or {}
    changes = report_data.get("changes") or []

    compact_changes = [
        {
            "title": change.get("title", ""),
            "category": change.get("category", ""),
            "impact_level": change.get("impact_level", "NONE"),
            "confidence": change.get("confidence", ""),
            "modules": change.get("modules", []),
            "actions": change.get("actions", []),
            "source_url": change.get("source_url", ""),
            "knowledge_id": change.get("knowledge_id"),
        }
        for change in changes
        if isinstance(change, dict)
    ]

    return REPORT_GENERATION_PROMPT.format(
        period_start=period.get("start", ""),
        period_end=period.get("end", ""),
        report_summary_json=json.dumps(summary, ensure_ascii=False, indent=2),
        report_changes_json=json.dumps(
            compact_changes,
            ensure_ascii=False,
            indent=2,
        ),
    )


def _build_report_output(
    content: dict,
    *,
    generated_at: str,
) -> dict:
    return {
        "title": REPORT_TITLE,
        "executive_summary": content.get("executive_summary", ""),
        "key_changes": content.get("key_changes", []),
        "risk_summary": content.get("risk_summary", ""),
        "generated_at": generated_at,
    }


def generate_weekly_report(
    report_data: dict,
    client=None,
) -> dict:
    generated_at = datetime.now().isoformat()
    ai_client = client or default_client

    if not report_data.get("changes"):
        return _build_report_output(
            DEFAULT_AI_REPORT_CONTENT.copy(),
            generated_at=generated_at,
        )

    prompt = _build_prompt(report_data)

    response = ai_client.responses.create(
        model=MODEL_NAME,
        input=prompt,
    )

    try:
        raw_result = json.loads(response.output_text)
        if not isinstance(raw_result, dict):
            raise json.JSONDecodeError("Expected object", response.output_text, 0)
        normalized = _normalize_ai_report_content(raw_result)
    except json.JSONDecodeError:
        print("AI weekly report generation returned invalid JSON.")
        print(response.output_text)
        normalized = DEFAULT_AI_REPORT_CONTENT.copy()

    return _build_report_output(normalized, generated_at=generated_at)
