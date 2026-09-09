import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from model_json import load_model_json
from object_dna_fixture import OBJECT_DNA_FIXTURE
from object_dna_service import generate_object_dna
from plan_schemas import PhysicalPlan
from plan_validator import (
    normalize_plan_item_ids,
    validate_inventory_grounding,
    validate_zero_plan,
)
from schemas import CertaintyLevel


load_dotenv()

api_key = os.getenv("NEBIUS_API_KEY")

if not api_key:
    raise RuntimeError("NEBIUS_API_KEY was not found in .env")


client = OpenAI(
    base_url="https://api.tokenfactory.us-central1.nebius.com/v1/",
    api_key=api_key,
)


MODEL = "nvidia/nemotron-3-super-120b-a12b"


GOAL = """
Create a practical tabletop product-photography setup for photographing
a small object.

The user already has a phone camera.

Constraints:
- Budget: $0.
- Use only the listed physical inventory objects.
- Do not assume any unlisted lamp, window, tape, tripod, stand, shelf,
  fastener, or other physical resource.
- No permanent modifications.
- Do not damage the listed objects.
- Prefer a simple setup that a normal person could actually assemble.
""".strip()


inventory_payload = [
    {
        "id": item.id,
        "name": item.name,
        "description": item.description,
    }
    for item in OBJECT_DNA_FIXTURE.items
]


VALID_ITEM_IDS = {
    item["id"]
    for item in inventory_payload
}


def call_planner(
    prompt: str,
) -> PhysicalPlan:
    response = client.chat.completions.create(
        model=MODEL,
        reasoning_effort="low",
        response_format={
            "type": "json_object"
        },
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0,
        max_tokens=4000,
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        raise RuntimeError(
            "Planner output was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            f"Planner refused request: "
            f"{choice.message.refusal}"
        )

    raw_output = choice.message.content

    if not raw_output:
        raise RuntimeError(
            "Planner returned no final content."
        )

    payload = load_model_json(
        raw_output
    )

    return PhysicalPlan.model_validate(
        payload
    )


# ---------------------------------------------------------------------------
# GENERIC BASELINE
# ---------------------------------------------------------------------------


baseline_prompt = f"""
You are solving a constrained physical problem.

Use creative but realistic reasoning.

Return ONLY valid JSON in EXACTLY this structure:

{{
  "title": "short plan title",
  "summary": "short summary",
  "item_ids_used": [
    "exact inventory ids"
  ],
  "steps": [
    {{
      "order": 1,
      "action": "specific physical action",
      "item_ids": [
        "exact inventory ids used in this step"
      ],
      "why_it_helps": "brief reason"
    }}
  ],
  "assumptions": [],
  "unresolved_risks": [],
  "constraint_check": []
}}

Rules:
- Use only inventory item IDs provided below.
- Do not invent physical resources.
- Do not recommend purchasing anything.
- Do not assume an unlisted window, lamp, tripod, tape, stand,
  fastener, shelf, or other physical object.
- The phone camera is already available and does not need an item ID.
- Maximum 8 steps.
- Be physically conservative.
- If something cannot be safely determined, state it in assumptions
  or unresolved_risks.
- Return JSON only.

Goal:

{GOAL}

Inventory:

{json.dumps(inventory_payload, indent=2)}
""".strip()


print("Running generic baseline...")

baseline_plan = call_planner(
    baseline_prompt
)

baseline_plan = normalize_plan_item_ids(
    baseline_plan
)

validate_inventory_grounding(
    baseline_plan,
    VALID_ITEM_IDS,
)

# ---------------------------------------------------------------------------
# GENERATE VALIDATED OBJECT DNA
# ---------------------------------------------------------------------------


print("Generating validated Object DNA...")

object_dna_objects = []

for item in OBJECT_DNA_FIXTURE.items:
    print(f"Generating DNA: {item.id}")

    dna = generate_object_dna(
        item
    )

    object_dna_objects.append(
        dna
    )


from schemas import ObjectDNAResponse


object_dna = ObjectDNAResponse(
    objects=object_dna_objects
)


# Give the planner medium/high-certainty capabilities.
# LOW certainty cannot authorize ZERO V1 actions anyway.

planner_dna_payload = []

for dna in object_dna.objects:
    planner_dna_payload.append(
        {
            "item_id": dna.item_id,

            "physical_traits": [
                trait.model_dump(mode="json")
                for trait in dna.physical_traits
                if trait.certainty != CertaintyLevel.LOW
            ],

            "affordances": [
                affordance.model_dump(mode="json")
                for affordance in dna.affordances
                if affordance.certainty != CertaintyLevel.LOW
            ],

            "unknown_properties": dna.unknown_properties,
            "caution_notes": dna.caution_notes,
        }
    )


# ---------------------------------------------------------------------------
# ZERO CAPABILITY-BOUND PLANNER
# ---------------------------------------------------------------------------


zero_prompt = f"""
You are ZERO's capability-bound physical planning layer.

ZERO is different from a normal language model:

You are NOT allowed to use an inventory object merely because you can
imagine a possible use for it.

Every physical use MUST be authorized by that item's validated Object DNA.

For every inventory item participating in a plan step, you MUST cite one
or more exact Object DNA capabilities that authorize the intended use.

Return ONLY valid JSON in EXACTLY this structure:

{{
  "title": "short plan title",
  "summary": "short summary",
  "item_ids_used": [
    "exact inventory ids"
  ],
  "steps": [
    {{
      "order": 1,
      "action": "specific physical action",
      "item_ids": [
        "exact inventory ids used in this step"
      ],
      "capability_uses": [
        {{
          "item_id": "exact inventory id",
          "capability": "exact capability from that item's Object DNA",
          "purpose": "how this exact capability authorizes the physical use"
        }}
      ],
      "why_it_helps": "brief reason"
    }}
  ],
  "assumptions": [],
  "unresolved_risks": [],
  "constraint_check": []
}}


HARD RULES

- Use only listed inventory IDs.

- Every item listed in a step's item_ids MUST have at least one
  capability_uses entry in that same step.

- capability MUST exactly match an affordance present in that item's
  validated Object DNA.

- Do NOT invent capabilities.

- Do NOT infer a new physical use from object identity alone.

Example:

If spray_bottles_01 has:
- contain
- dispense_liquid
- reposition

but does NOT have:
- provide_weight

then:

"use spray bottles as weights"

IS FORBIDDEN.

Do not propose it.

Likewise:

If an object has no capability supporting the intended action,
either use another object or change the plan.

- Low-certainty capabilities are not available to this planner.

- Respect unknown_properties.

- Respect caution_notes.

- Do not turn an unknown property into an assumption merely because
  it would make the plan convenient.

- Do not recommend buying anything.

- Do not assume:
  lamp
  window
  tape
  tripod
  stand
  shelf
  fastener
  or any other unlisted physical resource.

- The phone camera is already available and does not require
  an inventory ID.

- Budget is $0.

- No permanent modifications.

- No intentional damage.

- Maximum 8 steps.

- Prefer fewer well-grounded physical uses over more creative but
  weakly supported ones.

- Return JSON only.


Goal:

{GOAL}


Canonical inventory:

{json.dumps(inventory_payload, indent=2)}


Validated Object DNA:

{json.dumps(planner_dna_payload, indent=2)}
""".strip()


print("Running capability-bound ZERO planner...")

zero_plan = call_planner(
    zero_prompt
)

zero_plan = normalize_plan_item_ids(
    zero_plan
)


print("Validating ZERO plan...")

zero_plan = validate_zero_plan(
    zero_plan,
    object_dna,
    VALID_ITEM_IDS,
)


# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------


print()
print("=" * 70)
print("GENERIC BASELINE")
print("=" * 70)

print(
    baseline_plan.model_dump_json(
        indent=2
    )
)


print()
print("=" * 70)
print("CAPABILITY-BOUND ZERO")
print("=" * 70)

print(
    zero_plan.model_dump_json(
        indent=2
    )
)