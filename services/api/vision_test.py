import base64
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from model_json import parse_model_json
from schemas import VisionObservationResponse


load_dotenv()

api_key = os.getenv("NEBIUS_API_KEY")

if not api_key:
    raise RuntimeError("NEBIUS_API_KEY was not found in .env")


IMAGE_PATH = Path("sample_data/private/room-test-01.jpg")

if not IMAGE_PATH.exists():
    raise RuntimeError(f"Test image was not found: {IMAGE_PATH}")


image_bytes = IMAGE_PATH.read_bytes()
image_base64 = base64.b64encode(image_bytes).decode("utf-8")

data_url = f"data:image/jpeg;base64,{image_base64}"


client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=api_key,
)


response = client.chat.completions.create(
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

choice = response.choices[0]

print(f"finish_reason: {choice.finish_reason}")

if choice.finish_reason == "length":
    raise RuntimeError(
        "Vision model output was truncated because the output token limit was reached."
    )

raw_output = choice.message.content

if not raw_output:
    raise RuntimeError("Vision model returned no text output.")

validated = parse_model_json(
    raw_output,
    VisionObservationResponse,
)

print(validated.model_dump_json(indent=2))
