import json

from app.ai.analyzer import client
from app.core.config import MODEL_NAME


TV_PRODUCT_CONTEXT = """
Smart TV and connected device product scope:

Hardware modules:
- Display panel
- HDMI / USB ports
- Tuner (DVB / CI+)
- Network (Wi-Fi / Ethernet)
- Remote control / voice input

Software modules:
- OTA update
- Browser / HbbTV
- DRM
- Voice assistant
- AI features
- Network services
- Accessibility features
- Cybersecurity controls
- Energy efficiency settings
"""


IMPACT_ANALYSIS_PROMPT = """
You are an EU regulatory compliance expert specializing in Smart TV
and consumer electronics products.

Analyze ONLY the regulation content changes below.
Do not assume content outside the diff.

Monitor metadata:
- Name: {monitor_name}
- Category: {monitor_category}
- URL: {monitor_url}
- Keywords: {monitor_keywords}

{tv_product_context}

Rules:
1. Return ONLY valid JSON.
2. Do NOT use Markdown.
3. Base your assessment only on the changed content.
4. impact_level must be one of: HIGH, MEDIUM, LOW, NONE
5. confidence must be one of: HIGH, MEDIUM, LOW
6. affected_modules must list only TV hardware/software modules
   from the product context that are likely impacted.
7. recommended_actions must be short, actionable items for
   product compliance teams.

Changed content:

ADDED CONTENT:
{added_content}

REMOVED CONTENT:
{removed_content}

DIFF:
{diff_text}

Return JSON in this format:
{{
  "impact_level": "HIGH",
  "affected_modules": [],
  "reason": "",
  "recommended_actions": [],
  "confidence": "HIGH"
}}
"""


DEFAULT_IMPACT_RESULT = {
    "impact_level": "NONE",
    "affected_modules": [],
    "reason": "Unable to analyze change impact.",
    "recommended_actions": [],
    "confidence": "LOW",
}


def _normalize_level(value: str, allowed: set[str]) -> str:
    normalized = str(value).strip().upper()
    if normalized in allowed:
        return normalized
    return "NONE" if allowed == {"HIGH", "MEDIUM", "LOW", "NONE"} else "LOW"


def _normalize_impact_result(raw_result: dict) -> dict:
    return {
        "impact_level": _normalize_level(
            raw_result.get("impact_level", "NONE"),
            {"HIGH", "MEDIUM", "LOW", "NONE"},
        ),
        "affected_modules": [
            str(module).strip()
            for module in raw_result.get("affected_modules", [])
            if str(module).strip()
        ],
        "reason": str(raw_result.get("reason", "")).strip(),
        "recommended_actions": [
            str(action).strip()
            for action in raw_result.get("recommended_actions", [])
            if str(action).strip()
        ],
        "confidence": _normalize_level(
            raw_result.get("confidence", "LOW"),
            {"HIGH", "MEDIUM", "LOW"},
        ),
    }


def _format_diff_section(lines: list[str]) -> str:
    if not lines:
        return "(none)"
    return "\n".join(lines)


def _build_prompt(diff_result: dict, monitor: dict) -> str:
    return IMPACT_ANALYSIS_PROMPT.format(
        monitor_name=monitor.get("name", ""),
        monitor_category=monitor.get("category", ""),
        monitor_url=monitor.get("url", ""),
        monitor_keywords=", ".join(monitor.get("keywords", [])),
        tv_product_context=TV_PRODUCT_CONTEXT.strip(),
        added_content=_format_diff_section(
            diff_result.get("added_content", [])
        ),
        removed_content=_format_diff_section(
            diff_result.get("removed_content", [])
        ),
        diff_text=diff_result.get("diff_text", "") or "(none)",
    )


def analyze_change_impact(diff_result: dict, monitor: dict) -> dict:
    prompt = _build_prompt(diff_result, monitor)

    response = client.responses.create(
        model=MODEL_NAME,
        input=prompt,
    )

    try:
        raw_result = json.loads(response.output_text)
        return _normalize_impact_result(raw_result)
    except json.JSONDecodeError:
        print("AI impact analysis returned invalid JSON.")
        print(response.output_text)
        return DEFAULT_IMPACT_RESULT.copy()
