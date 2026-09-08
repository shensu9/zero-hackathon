import os

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

api_key = os.getenv("NEBIUS_API_KEY")

if not api_key:
    raise RuntimeError("NEBIUS_API_KEY was not found in .env")

client = OpenAI(
    base_url="https://api.tokenfactory.us-central1.nebius.com/v1/",
    api_key=api_key,
)

models = client.models.list()

matches = sorted(
    model.id
    for model in models.data
    if (
        "nvidia" in model.id.lower()
        or "nemotron" in model.id.lower()
        or "omni" in model.id.lower()
    )
)

if matches:
    print("Available NVIDIA / Nemotron models:")
    for model_id in matches:
        print(model_id)
else:
    print("No NVIDIA / Nemotron models returned by this endpoint.")