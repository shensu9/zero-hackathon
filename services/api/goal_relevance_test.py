import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from inventory import build_canonical_inventory
from model_json import parse_model_json
from schemas import (
    GoalAwareInventoryResponse,
    GoalInput,
    VisionObservationResponse,
)


load_dotenv()

api_key = os.getenv("NEBIUS_API_KEY")

if not api_key:
    raise RuntimeError("NEBIUS_API_KEY was not found in .env")


IMAGE_PATH = Path("sample_data/private/room-test-01.jpg")

if not IMAGE_PATH.exists():
    raise RuntimeError(f"Test image was not found: {IMAGE_PATH}")


goal = GoalInput(
    primary_goal="Create a $0 product photography setup",
    budget_dollars=0,
    permanent_modifications_allowed=False,
)


image_bytes = IMAGE_PATH.read_bytes()
image_base64 = base64.b64encode(image_bytes).decode("utf-8")
data_url = f"data:image/jpeg;base64,{image_base64}"


vision_client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=api_key,
)

reasoning_client = OpenAI(
    base_url="https://api.tokenfactory.us-central1.nebius.com/v1/",
    api_key=api_key,
)


vision_response = vision_client.chat.completions.create(
    model="MiniMaxAI/MiniMax-M3",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": """
You are the perception layer for a project called ZERO.

Inspect the supplied image carefully.

Return ONLY valid JSON with this structure:

{
  "objects": [
    {
      "name": "short object name",
      "description": "brief visually grounded description",
      "location_hint": "where it appears in the scene",
      "potentially_useful": true,
      "confidence": 0.0
    }
  ]
}

Rules:
- Report only physical objects that are actually visible.
- Do not invent hidden objects.
- Prefer objects that could potentially be reused to solve a physical task.
- Do not infer capabilities yet.
- Do not suggest solutions.
- Do not include people as usable objects.
- Confidence must be between 0 and 1.
""".strip(),
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": data_url
                    },
                },
            ],
        }
    ],
    temperature=0,
    max_tokens=3000,
)

vision_choice = vision_response.choices[0]
print(f"vision finish_reason: {vision_choice.finish_reason}")

if vision_choice.finish_reason == "length":
    raise RuntimeError(
        "Vision model output was truncated because the output token limit was reached."
    )

vision_raw_output = vision_choice.message.content

if not vision_raw_output:
    raise RuntimeError("Vision model returned no text output.")

validated_observations = parse_model_json(
    vision_raw_output,
    VisionObservationResponse,
)

inventory = build_canonical_inventory(validated_observations)


reasoning_response = reasoning_client.chat.completions.create(
    model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    reasoning_effort="low",
    response_format={
        "type": "json_object"
    },
    messages=[
        {
            "role": "user",
            "content": f"""
You are ZERO's reasoning layer.

Your task is to judge which inventory items matter for the user's goal.

Return ONLY valid JSON with this structure:

{{
  "items": [
    {{
      "item_id": "exact inventory item id",
      "relevance": "relevant | possibly_relevant | not_relevant",
      "reason": "reason in 12 words or fewer"
    }}
  ]
}}

Rules:
- Include every inventory item exactly once.
- Use the provided item_id values exactly as written.
- Judge relevance only in relation to the user's goal.
- "relevant" means likely useful for accomplishing the goal.
- "possibly_relevant" means may help, but is optional, uncertain, or indirect.
- "not_relevant" means unlikely to matter for this goal.
- Do not invent items.
- Do not make a step-by-step solution yet.
- Do not output markdown fences.
- Keep every reason to 12 words or fewer.
User goal:
{goal.model_dump_json(indent=2)}

Canonical inventory:
{inventory.model_dump_json(indent=2)}
""".strip(),
        }
    ],
    temperature=0,
    max_tokens=4000,
)

reasoning_choice = reasoning_response.choices[0]
print(f"reasoning finish_reason: {reasoning_choice.finish_reason}")

if reasoning_choice.finish_reason == "length":
    raise RuntimeError(
        "Reasoning model output was truncated because the output token limit was reached."
    )

reasoning_raw_output = reasoning_choice.message.content

if not reasoning_raw_output:
    raise RuntimeError("Reasoning model returned no text output.")

goal_aware_inventory = parse_model_json(
    reasoning_raw_output,
    GoalAwareInventoryResponse,
)

print(goal_aware_inventory.model_dump_json(indent=2))