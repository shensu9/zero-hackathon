import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from json_format_repair import load_or_repair_json
from plan_normalizer import (
    normalize_external_resource_ids,
    normalize_plan_payload,
)
from plan_outcome_schemas import (
    PlanOutcome,
)
from plan_validator import (
    normalize_plan_item_ids,
)
from schemas import (
    CertaintyLevel,
    InventoryItem,
    ObjectDNAResponse,
)


load_dotenv()

api_key = os.getenv("NEBIUS_API_KEY")

if not api_key:
    raise RuntimeError(
        "NEBIUS_API_KEY was not found in .env"
    )


client = OpenAI(
    base_url=(
        "https://api.tokenfactory."
        "us-central1.nebius.com/v1/"
    ),
    api_key=api_key,
)


MODEL = "nvidia/nemotron-3-super-120b-a12b"


# ---------------------------------------------------------------------------
# COMPACT WORLD MODEL
# ---------------------------------------------------------------------------


def _build_compact_world_model(
    object_dna: ObjectDNAResponse,
) -> list[dict]:
    result = []

    for dna in object_dna.objects:
        result.append(
            {
                "item_id":
                    dna.item_id,

                "traits": [
                    trait.trait.value
                    for trait in dna.physical_traits
                    if (
                        trait.certainty
                        != CertaintyLevel.LOW
                    )
                ],

                "capabilities": [
                    affordance.capability.value
                    for affordance in dna.affordances
                    if (
                        affordance.certainty
                        != CertaintyLevel.LOW
                    )
                ],

                "unknown_properties":
                    dna.unknown_properties,

                "caution_notes":
                    dna.caution_notes,
            }
        )

    return result


# ---------------------------------------------------------------------------
# PAYLOAD NORMALIZATION
# ---------------------------------------------------------------------------


def _normalize_outcome_payload(
    payload: dict,
) -> dict:
    """
    Normalize only harmless structural plan details before Pydantic
    validates the complete PlanOutcome.

    Outcome status/requirements/blockers are never inferred here.
    """

    plan_payload = payload.get(
        "plan"
    )

    if isinstance(
        plan_payload,
        dict,
    ):
        payload["plan"] = (
            normalize_plan_payload(
                plan_payload
            )
        )

    return payload


def _normalize_outcome_plan(
    outcome: PlanOutcome,
    external_resources,
) -> PlanOutcome:
    """
    Apply the same structural inventory-ID conventions used elsewhere
    in ZERO.

    Explicit external resources are removed from inventory-ID fields,
    but arbitrary unknown resources are preserved for hard validation.
    """

    if outcome.plan is None:
        return outcome

    plan = (
        normalize_external_resource_ids(
            outcome.plan,
            external_resources,
        )
    )

    plan = normalize_plan_item_ids(
        plan
    )

    return outcome.model_copy(
        update={
            "plan": plan,
        }
    )


# ---------------------------------------------------------------------------
# OUTCOME-AWARE ZERO PLANNER
# ---------------------------------------------------------------------------


def generate_plan_outcome(
    *,
    goal: str,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
    external_resources=None,
) -> PlanOutcome:
    """
    Ask ZERO to decide whether the goal is:

    - solved now
    - conditionally solvable
    - blocked pending confirmation
    - not safely solvable

    This does not replace deterministic PhysicalPlan validation.
    """

    external_resources = list(
        external_resources
        or []
    )

    inventory_payload = [
        {
            "id":
                item.id,

            "name":
                item.name,

            "description":
                item.description,
        }
        for item in inventory
    ]

    world_model = (
        _build_compact_world_model(
            object_dna
        )
    )

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
You are ZERO's outcome-aware physical planning layer.

ZERO reasons over a validated physical world model.

Your first responsibility is NOT to force a plan.

Your first responsibility is to decide whether the user's goal:

1. can be executed now,
2. can be executed only after a concrete requirement is verified,
3. needs missing information before a plan can even be selected,
4. or cannot safely be solved with the available resources.


Return ONLY valid JSON in exactly this top-level structure:

{{
  "status": "solved | conditional | needs_confirmation | cannot_safely_solve",

  "explanation": "brief explanation of why this status applies",

  "plan": null,

  "requirements": [],

  "blocking_reasons": []
}}


======================================================================
STATUS SEMANTICS
======================================================================


SOLVED

Use "solved" only when:

- a grounded executable physical plan is available now,
- there are no unresolved prerequisites,
- there are no safety-critical unknowns that must be resolved first.

For SOLVED:

- plan MUST contain a PhysicalPlan.
- requirements MUST be [].
- blocking_reasons MUST be [].


CONDITIONAL

Use "conditional" when:

- ZERO already knows what physical plan should be executed,
- but one or more concrete requirements must be verified BEFORE
  execution,
- and satisfying those requirements would make the plan executable.

Examples:

- electrical rating must be verified compatible before powered use
- unknown liquid contents must be identified as appropriate before
  dispensing
- a user-provided environmental condition must be confirmed before
  execution

For CONDITIONAL:

- plan MUST contain the plan that becomes executable only AFTER all
  requirements are satisfied.
- requirements MUST contain at least one requirement.
- blocking_reasons MUST be [].

IMPORTANT:

Do NOT put the unresolved verification itself into the executable
PhysicalPlan merely to satisfy the plan schema.

The requirement belongs in "requirements".

The PhysicalPlan describes what happens AFTER the requirement is met.


NEEDS_CONFIRMATION

Use "needs_confirmation" when:

- information is missing,
- and ZERO cannot yet determine which physical plan should be selected.

Example:

The solution depends on whether the user wants object A protected or
object B protected, but the goal does not specify which.

For NEEDS_CONFIRMATION:

- plan MUST be null.
- requirements MUST contain the question/fact that must be resolved.
- blocking_reasons MUST be [].


CANNOT_SAFELY_SOLVE

Use "cannot_safely_solve" when:

- the required physical capability is absent,
- constraints make the goal impossible,
- or no verification/confirmation could turn the current inventory
  into a grounded safe solution.

For CANNOT_SAFELY_SOLVE:

- plan MUST be null.
- requirements MUST be [].
- blocking_reasons MUST contain at least one concrete reason.


======================================================================
REQUIREMENT STRUCTURE
======================================================================

Each requirement must be:

{{
  "requirement": "what must become known or true",
  "how_to_verify": "how the user can determine whether it is satisfied",
  "if_not_met": "what ZERO must do if the requirement fails"
}}

Verification actions such as:

- inspect
- check
- confirm
- read a label
- identify contents

are not automatically new physical resources.

Do not invent a tool unless the verification explicitly requires one.


======================================================================
PHYSICAL PLAN STRUCTURE
======================================================================

Whenever "plan" is not null, use exactly:

{{
  "title": "short plan title",

  "summary": "short grounded summary",

  "item_ids_used": [
    "canonical inventory IDs only"
  ],

  "steps": [
    {{
      "order": 1,

      "action": "specific physical action",

      "item_ids": [
        "canonical inventory IDs used in this step"
      ],

      "capability_uses": [
        {{
          "item_id": "exact canonical inventory ID",

          "capability": "exact capability from the validated world model",

          "purpose": "brief explanation of the authorized physical use"
        }}
      ],

      "why_it_helps": "brief grounded reason"
    }}
  ],

  "assumptions": [],

  "unresolved_risks": [],

  "constraint_check": []
}}


======================================================================
PHYSICAL GROUNDING RULES
======================================================================

- Use only canonical inventory objects and explicit external resources.

- External resources may appear naturally in action text.

- External resources must NOT be put into item_ids.

- Every inventory object used in a plan step must cite at least one
  exact validated capability.

- Do not invent capabilities.

- Do not stretch one capability into a different physical behavior.

- Low-certainty capabilities are unavailable.

- Unknown properties remain unknown.

- Safety cautions remain active.

- Never convert an unknown property into a convenient assumption.

- If an unknown property must be verified before execution, prefer a
  CONDITIONAL outcome.

- Do not manufacture a fake executable step merely because PhysicalPlan
  normally requires at least one step.

- Maximum 6 plan steps.

- Keep wording concise.


======================================================================
IMPORTANT EXAMPLES
======================================================================


EXAMPLE A — CONDITIONAL

World model:

spray_bottle_01:
- capability: dispense_liquid
- unknown property: current liquid contents

Goal:

Spray the liquid onto a surface, but only if contents are appropriate.

Correct reasoning:

status = conditional

requirement:
Identify the current liquid contents and confirm they are appropriate.

plan:
After that requirement passes, use dispense_liquid to spray.

Do NOT assume the liquid is water.

Do NOT return zero plan steps.


EXAMPLE B — CANNOT SAFELY SOLVE

Goal requires hanging an object from the ceiling.

No available object provides a grounded hanging/fastening relationship
and no external support is available.

Correct reasoning:

status = cannot_safely_solve
plan = null


======================================================================
USER GOAL
======================================================================

{goal}


======================================================================
EXPLICIT EXTERNAL RESOURCES
======================================================================

{json.dumps(external_resources, indent=2)}


======================================================================
CANONICAL INVENTORY
======================================================================

{json.dumps(inventory_payload, indent=2)}


======================================================================
VALIDATED PHYSICAL WORLD MODEL
======================================================================

{json.dumps(world_model, indent=2)}


Return JSON only.
""".strip(),
            }
        ],

        temperature=0,
        max_tokens=5000,
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        raise RuntimeError(
            "Plan outcome output was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            "Plan outcome generation was refused: "
            f"{choice.message.refusal}"
        )

    raw_output = choice.message.content

    if not raw_output:
        raise RuntimeError(
            "Plan outcome generation returned no final content."
        )

    payload = load_or_repair_json(
        raw_output
    )

    payload = _normalize_outcome_payload(
        payload
    )

    outcome = PlanOutcome.model_validate(
        payload
    )

    return _normalize_outcome_plan(
        outcome,
        external_resources,
    )