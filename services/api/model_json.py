import json
from typing import Any

from pydantic import BaseModel


def _strip_json_fences(text: str) -> str:
    cleaned = text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):].strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    return cleaned


def load_model_json(text: str) -> dict[str, Any]:
    cleaned = _strip_json_fences(text)

    data = json.loads(cleaned)

    if not isinstance(data, dict):
        raise ValueError(
            "Expected model JSON output to contain a top-level object."
        )

    return data


def parse_model_json(
    text: str,
    schema: type[BaseModel],
) -> BaseModel:
    data = load_model_json(text)

    return schema.model_validate(data)