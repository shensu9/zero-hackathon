import json

from pydantic import BaseModel


def parse_model_json(text: str, schema: type[BaseModel]) -> BaseModel:
    cleaned = text.strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):].strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    data = json.loads(cleaned)

    return schema.model_validate(data)