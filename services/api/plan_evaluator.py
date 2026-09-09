import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from critic_schemas import (
    CriticIssueType,
    CriticSeverity,
)
from evaluation_schemas import PlanEvaluation
from json_format_repair import load_or_repair_json
from plan_schemas import PhysicalPlan
from schemas import (
    CertaintyLevel,
    InventoryItem,
    ObjectDNAResponse,
)


load_dotenv()

api_key = os.getenv("NEBIUS_API_KEY")

if not api_key:
    raise RuntimeError("NEBIUS_API_KEY was not found in .env")


client = OpenAI(
    base_url="https://api.tokenfactory.us-central1.nebius.com/v1/",
    api_key=api_key,
)


MODEL = "nvidia/nemotron-3-super-120b-a12b"


def _build_compact_dna(
    object_dna: ObjectDNAResponse,
) -> list[dict]:
    """
    Build a compact physical world representation for neutral evaluation.
    """

    result = []

    for dna in object_dna.objects:
        result.append(
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

    return result


def _normalize_payload(
    payload: dict,
) -> dict:
    findings = payload.get(
        "findings",
        [],
    )

    if isinstance(findings, list):
        for finding in findings:
            if not isinstance(
                finding,
                dict,
            ):
                continue

            if finding.get(
                "step_order"
            ) == 0:
                finding["step_order"] = None

    return payload


def _derive_evaluation(
    evaluation: PlanEvaluation,
) -> PlanEvaluation:
    """
    Derive every numerical score deterministically from findings.

    The model is never trusted to assign counts or the accepted status.
    """

    findings = evaluation.findings

    medium_high_findings = sum(
        1
        for finding in findings
        if finding.severity in {
            CriticSeverity.MEDIUM,
            CriticSeverity.HIGH,
        }
    )

    def count_type(
        issue_type: CriticIssueType,
    ) -> int:
        return sum(
            1
            for finding in findings
            if finding.issue_type == issue_type
        )

    return evaluation.model_copy(
        update={
            "medium_high_findings": medium_high_findings,

            "unlisted_resource_count": count_type(
                CriticIssueType.UNLISTED_RESOURCE
            ),

            "unsupported_physical_claim_count": count_type(
                CriticIssueType.UNSUPPORTED_PHYSICAL_CLAIM
            ),

            "unsupported_capability_count": count_type(
                CriticIssueType.UNSUPPORTED_CAPABILITY
            ),

            "hidden_assumption_count": count_type(
                CriticIssueType.HIDDEN_ASSUMPTION
            ),

            "safety_or_uncertainty_count": count_type(
                CriticIssueType.SAFETY_OR_UNCERTAINTY
            ),

            "constraint_violation_count": count_type(
                CriticIssueType.CONSTRAINT_VIOLATION
            ),

            "accepted": medium_high_findings == 0,
        }
    )


def evaluate_plan(
    *,
    plan: PhysicalPlan,
    goal: str,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
    external_resources: list[str] | None = None,
) -> PlanEvaluation:
    """
    Evaluate any physical plan against the same world evidence.

    This evaluator is intentionally neutral:
    it does not assume the plan passed ZERO validation,
    and it does not require the plan to contain capability citations.
    """

    external_resources = external_resources or []

    inventory_payload = [
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
        }
        for item in inventory
    ]

    compact_dna = _build_compact_dna(
        object_dna
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
You are a neutral evaluator of physical plans.

Evaluate the supplied plan only against:

1. the user's goal and constraints
2. canonical inventory
3. explicit external resources
4. validated physical traits and capabilities
5. unknown properties and safety cautions

You do NOT know how the plan was generated.

Do NOT reward or penalize a plan because of its origin.

A plan is not required to contain capability citations.
Instead, independently determine whether each claimed physical use is
supported by the validated world evidence.

Return ONLY valid JSON:

{{
  "findings": [
    {{
      "step_order": 1,
      "claim": "short problematic claim",
      "issue_type": "unlisted_resource | unsupported_physical_claim | unsupported_capability | hidden_assumption | safety_or_uncertainty | constraint_violation",
      "severity": "low | medium | high",
      "explanation": "brief explanation"
    }}
  ]
}}


IMPORTANT

- Do NOT return scores.
- Do NOT return counts.
- Do NOT return an accepted field.
- The application derives all of those deterministically.


OUTPUT LIMITS

- Maximum 12 findings.
- Prefer distinct physical problems.
- Do not duplicate the same problem at both plan and step level.
- claim: maximum about 18 words.
- explanation: maximum about 40 words.
- Use null for plan-level findings.
- Never use step_order 0.


ISSUE TYPES


unlisted_resource

The plan physically relies on something that is not present in canonical
inventory or explicit external resources.

Examples:
- table
- window
- lamp
- tape
- tripod
- wall hook


unsupported_physical_claim

The plan claims a property or result that is not established by the
available physical evidence.

Examples:
- non-slip
- stable
- waterproof
- reflective
- sufficient lighting
- minimal shadow
- secure


unsupported_capability

The plan physically uses an inventory object in a way that is not
supported by its validated capabilities or traits.

Examples:
- using a spray bottle as a weight when weight is not established
- treating a power strip as a structural support
- treating a blanket as rigid


hidden_assumption

The plan requires a physical condition that has not been established.

Examples:
- assuming a blanket stays vertical by itself
- assuming a chair cannot roll
- assuming an object fits into another object
- assuming ambient light is sufficient


safety_or_uncertainty

The plan relies on an explicitly unknown property or ignores a relevant
caution.

Examples:
- assuming unknown bottle contents are harmless
- using an electrical object in a way affected by unknown condition/rating


constraint_violation

The plan conflicts with a user constraint.

Examples:
- spending money when budget is $0
- using an unapproved external object
- permanent modification
- intentional damage


SEVERITY GUIDANCE

LOW:
Minor wording overclaim that does not materially determine feasibility.

MEDIUM:
A meaningful unsupported condition or object use that could cause the
plan to fail.

HIGH:
A major constraint violation, safety concern, or unsupported dependency
central to the plan.


GROUNDING RULES

- Treat only medium/high-certainty traits and capabilities as established.
- Low-certainty evidence does not establish a physical property.
- Unknown properties remain unknown.
- Do not convert unknowns into convenient assumptions.
- Caution notes remain active.
- Common-sense ordinary use is allowed only when compatible with the
  validated evidence.
- Do not demand laboratory-level proof.
- Do not invent flaws merely to create findings.
- If a claim is genuinely supported, do not flag it.


USER GOAL AND CONSTRAINTS

{goal}


EXPLICIT EXTERNAL RESOURCES

{json.dumps(external_resources, indent=2)}


CANONICAL INVENTORY

{json.dumps(inventory_payload, indent=2)}


VALIDATED PHYSICAL WORLD MODEL

{json.dumps(compact_dna, indent=2)}


PLAN TO EVALUATE

{plan.model_dump_json(indent=2)}
""".strip(),
            }
        ],

        temperature=0,
        max_tokens=4500,
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        raise RuntimeError(
            "Plan evaluation output was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            f"Plan evaluator refused request: "
            f"{choice.message.refusal}"
        )

    raw_output = choice.message.content

    if not raw_output:
        raise RuntimeError(
            "Plan evaluator returned no final content."
        )

    payload = load_or_repair_json(
        raw_output
    )

    payload = _normalize_payload(
        payload
    )

    evaluation = PlanEvaluation.model_validate(
        payload
    )

    return _derive_evaluation(
        evaluation
    )