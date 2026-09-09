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
from schemas import (
    CertaintyLevel,
    ObjectDNAResponse,
)
from semantic_critic import audit_plan_semantics


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
  fastener, table, tabletop, or other physical resource.
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
      "capability_uses": [],
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
  shelf, table, tabletop, fastener, or other physical object.
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


object_dna = ObjectDNAResponse(
    objects=object_dna_objects
)


planner_dna_payload = []

for dna in object_dna.objects:
    planner_dna_payload.append(
        {
            "item_id": dna.item_id,

            "traits": [
                trait.trait.value
                for trait in dna.physical_traits
                if trait.certainty != CertaintyLevel.LOW
            ],

            "capabilities": [
                affordance.capability.value
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

You are NOT allowed to use an inventory object merely because you can
imagine a possible use for it.

Every physical use MUST be authorized by that item's validated Object DNA.

For every inventory item participating in a plan step, cite one or more
exact Object DNA capabilities authorizing that use.

Return ONLY valid JSON in EXACTLY this structure:

{{
  "title": "short plan title",
  "summary": "short grounded summary",
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
          "purpose": "how this capability authorizes the physical use"
        }}
      ],
      "why_it_helps": "brief grounded reason"
    }}
  ],
  "assumptions": [],
  "unresolved_risks": [],
  "constraint_check": []
}}


HARD RULES

- Use only listed inventory IDs.

- Every inventory item used in a step must cite at least one validated
  Object DNA capability.

- The capability must exactly exist for that item.

- Do NOT invent capabilities.

- Do NOT infer a new physical use from object identity alone.

- Low-certainty capabilities are unavailable.

- Respect unknown_properties.

- Respect caution_notes.

- Do not convert an unknown property into an assumption just because
  it would make the plan easier.

- Do not claim physical properties that Object DNA does not establish.

Examples of forbidden unsupported claims:
- "non-slip" without friction evidence
- "well-lit" without illumination evidence
- "minimal shadow" without lighting evidence
- "stable" unless relevant support/stability is grounded
- "reflective" without reflect_light evidence
- "diffused light" without diffuse_light evidence

- Do not assume:
  lamp
  window
  tape
  tripod
  stand
  shelf
  table
  tabletop
  fastener
  or any other unlisted physical resource.

- The phone camera is explicitly available externally.

- Budget is $0.
- No permanent modifications.
- No intentional damage.
- Maximum 8 steps.

Return JSON only.


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


print("Running deterministic ZERO validation...")

zero_plan = validate_zero_plan(
    zero_plan,
    object_dna,
    VALID_ITEM_IDS,
)


# ---------------------------------------------------------------------------
# ZERO SEMANTIC CRITIC
# ---------------------------------------------------------------------------


print("Running ZERO semantic critic...")

critic_result = audit_plan_semantics(
    plan=zero_plan,
    goal=GOAL,
    inventory=OBJECT_DNA_FIXTURE.items,
    object_dna=object_dna,
    external_resources=[
        "phone camera",
    ],
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


print()
print("=" * 70)
print("ZERO SEMANTIC CRITIC")
print("=" * 70)

print(
    critic_result.model_dump_json(
        indent=2
    )
)


if not critic_result.passed:
    print()
    print(
        "ZERO PLAN STATUS: REJECTED BY SEMANTIC CRITIC"
    )
else:
    print()
    print(
        "ZERO PLAN STATUS: ACCEPTED"
    )