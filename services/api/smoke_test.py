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

response = client.chat.completions.create(
    model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    messages=[
        {
            "role": "user",
            "content": (
                'Reply with exactly this JSON and nothing else: '
                '{"status":"ok","project":"ZERO"}'
            ),
        }
    ],
    temperature=0,
)

print(response.choices[0].message.content)