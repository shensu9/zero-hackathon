import os
from json import JSONDecodeError

from dotenv import load_dotenv
from openai import OpenAI

from model_json import load_model_json


load_dotenv()

api_key = os.getenv("NEBIUS_API_KEY")

if not api_key:
    raise RuntimeError("NEBIUS_API_KEY was not found in .env")


client = OpenAI(
    base_url="https://api.tokenfactory.us-central1.nebius.com/v1/",
    api_key=api_key,
)


MODEL = "nvidia/nemotron-3-super-120b-a12b"


def repair_json_format(
    raw_output: str,
) -> dict:
    """
    Repair malformed JSON syntax only.

    This must not change the intended plan, add ideas,
    remove content, or reinterpret physical meaning.
    """

    response = client.chat.completions.create(
        model=MODEL,
        reasoning_effort="low",

        response_format={
            "type": "json_object"
        },

        messages=[
            {
                "role": "user",
                "content": f"""
You are a JSON syntax-repair tool.

The text below was intended to be valid JSON but contains formatting
or escaping errors.

Repair ONLY the JSON syntax.

Examples of allowed fixes:
- escape illegal control characters inside strings
- fix broken quotation marks
- fix missing commas or brackets
- remove markdown code fences

STRICT RULES:

- Preserve the original keys.
- Preserve the original values and meaning.
- Do NOT invent new plan steps.
- Do NOT remove plan steps.
- Do NOT improve the plan.
- Do NOT rewrite physical claims.
- Do NOT change capabilities.
- Do NOT add safety advice.
- Do NOT reinterpret the content.

Return only valid JSON.

Malformed JSON:

{raw_output}
""".strip(),
            }
        ],

        temperature=0,
        max_tokens=4000,
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        raise RuntimeError(
            "JSON formatting repair was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            f"JSON formatting repair refused request: "
            f"{choice.message.refusal}"
        )

    repaired_output = choice.message.content

    if not repaired_output:
        raise RuntimeError(
            "JSON formatting repair returned no content."
        )

    return load_model_json(
        repaired_output
    )


def load_or_repair_json(
    raw_output: str,
) -> dict:
    """
    Parse normally first.

    Only spend an additional model call if the response is actually
    malformed JSON.
    """

    try:
        return load_model_json(
            raw_output
        )

    except JSONDecodeError:
        print(
            "Model returned malformed JSON; "
            "attempting one formatting repair..."
        )

        return repair_json_format(
            raw_output
        )