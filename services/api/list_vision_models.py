import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

api_key = os.getenv("NEBIUS_API_KEY")

if not api_key:
    raise RuntimeError("NEBIUS_API_KEY was not found in .env")

client = OpenAI(
    base_url="https://api.tokenfactory.nebius.com/v1/",
    api_key=api_key,
)

models = client.models.list()

keywords = (
    "cosmos",
    "omni",
    "vision",
    "vl",
    "qwen2.5",
    "minimax",
)

matches = sorted(
    model.id
    for model in models.data
    if any(keyword in model.id.lower() for keyword in keywords)
)

print(f"Total models available: {len(models.data)}")
print()

if matches:
    print("Possible vision / multimodal models:")
    for model_id in matches:
        print(model_id)
else:
    print("No likely vision models matched.")