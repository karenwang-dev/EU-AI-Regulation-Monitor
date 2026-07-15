from openai import OpenAI

from app.core.config import (
    OPENAI_API_KEY,
    MODEL_NAME
)


REGULATION_SCHEMA = {
    "type": "object",
    "properties": {
        "website": {"type": "string"},
        "title": {"type": "string"},
        "publish_date": {"type": "string"},
        "summary": {"type": "string"},
        "category": {"type": "string"},
        "impact_level": {"type": "string"},
        "impact_reason": {"type": "array", "items": {"type": "string"}},
        "affected_products": {"type": "array", "items": {"type": "string"}},
        "affected_modules": {"type": "array", "items": {"type": "string"}},
        "actions_required": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "website",
        "title",
        "publish_date",
        "summary",
        "category",
        "impact_level",
        "impact_reason",
        "affected_products",
        "affected_modules",
        "actions_required",
    ],
    "additionalProperties": False,
}


client = OpenAI(
    api_key=OPENAI_API_KEY
)


def ask_ai(prompt: str):

    response = client.responses.create(

        model=MODEL_NAME,

        input=prompt,

        text={
            "format": {
                "type": "json_schema",
                "name": "regulation_analysis",
                "schema": REGULATION_SCHEMA,
                "strict": True
            }
        }
    )

    return response.output_text