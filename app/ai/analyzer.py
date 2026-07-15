import json

from openai import OpenAI

from app.core.config import (
    OPENAI_API_KEY,
    MODEL_NAME
)

from app.ai.prompts import REGULATION_ANALYSIS_PROMPT

client = OpenAI(
    api_key=OPENAI_API_KEY
)


def analyze_content(content: str) -> dict:

    prompt = REGULATION_ANALYSIS_PROMPT.format(
        content=content
    )

    response = client.responses.create(
        model=MODEL_NAME,
        input=prompt
    )

    try:

        return json.loads(
            response.output_text
        )

    except json.JSONDecodeError:

        print("AI 返回的 JSON 格式错误！")

        print(response.output_text)

        return {
            "website": "",
            "title": "",
            "publish_date": "",
            "summary": "JSON Parse Error",
            "category": "",
            "impact_level": "None",
            "affected_products": [],
            "actions_required": []
        }