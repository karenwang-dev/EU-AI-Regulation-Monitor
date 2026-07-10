import json

from app.ai_client import ask_ai
from app.prompts import REGULATION_ANALYSIS_PROMPT


def analyze_content(content: str):

    prompt = REGULATION_ANALYSIS_PROMPT.format(
        content=content
    )

    result = ask_ai(prompt)

    return json.loads(result)