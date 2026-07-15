from openai import OpenAI

from app.core.config import (
    OPENAI_API_KEY,
    MODEL_NAME
)


client = OpenAI(
    api_key=OPENAI_API_KEY
)



PROMPT = """

You are an EU regulatory compliance expert
for Smart TV and consumer electronics.

Analyze the following website change.

Determine:

1. Is this related to regulations?
2. Which category?
3. Impact level.
4. Affected products.
5. Recommended action.


Return JSON only:

{{
"is_regulation_related": "",
"category": "",
"impact_level": "",
"affected_products": [],
"summary": "",
"recommended_action": ""
}}


CHANGE:

{diff}

"""



def analyze_change(diff):


    response = client.responses.create(

        model=MODEL_NAME,

        input=PROMPT.format(
            diff=diff
        )

    )


    return response.output_text