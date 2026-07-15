from openai import OpenAI

from app.config import (
    OPENAI_API_KEY,
    MODEL_NAME
)

from app.schemas import REGULATION_SCHEMA


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