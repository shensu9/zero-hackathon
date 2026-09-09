import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from critic_schemas import (
    CriticSeverity,
    PlanCriticResult,
)
from model_json import load_model_json
from plan_schemas import PhysicalPlan
from schemas import (
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


def audit_plan_semantics(
    *,
    plan: PhysicalPlan,
    goal: str,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
    external_resources: list[str] | None = None,
) -> PlanCriticResult:
    """
    Audit a capability-bound ZERO plan for semantic physical claims
    that deterministic capability validation cannot easily detect.

    Examples:
    - relying on an unlisted tabletop
    - claiming a blanket is non-slip
    - claiming a setup is well-lit without a grounded light source
    - assuming unsupported stability, strength, dimensions, etc.
    """

    external_resources = external_resources or []

    inventory_payload = [
        item.model_dump(mode="json")
        for item in inventory
    ]

    dna_payload = [
        dna.model_dump(mode="json")
        for dna in object_dna.objects
    ]

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
You are ZERO's semantic physical-plan critic.

ZERO has already performed deterministic checks that:
- inventory item IDs exist
- every physical item use cites an Object DNA capability
- the cited capability exists

Your job is DIFFERENT.

Audit the actual LANGUAGE and physical claims in the plan.

Find hidden or unsupported claims that can still appear in:
- title
- summary
- action text
- capability purpose text
- why_it_helps
- assumptions
- unresolved risks
- constraint checks


Return ONLY valid JSON in EXACTLY this structure:

{{
  "passed": false,
  "findings": [
    {{
      "step_order": 1,
      "claim": "short exact or near-exact problematic claim",
      "issue_type": "unlisted_resource | unsupported_physical_claim | unsupported_capability | hidden_assumption | safety_or_uncertainty | constraint_violation",
      "severity": "low | medium | high",
      "explanation": "why the claim is not grounded",
      "recommended_fix": "specific correction"
    }}
  ]
}}


STEP ORDER RULE

- Use the actual step number when a finding belongs to one specific step.
- Use null when the finding applies to the title, summary, overall plan,
  assumptions, risks, or the plan generally.
- Never use 0 as a step_order.


WHEN TO PASS

passed should be true only when there are no meaningful unsupported
physical claims.

Do not invent findings merely to be critical.


ISSUE TYPES

unlisted_resource:
The plan functionally relies on a physical resource that is not in
the canonical inventory or explicitly listed as an external resource.

Examples:
- tabletop
- lamp
- window
- tape
- tripod
- shelf

Do not flag abstract things such as gravity, air, or ordinary room space
unless the plan makes a meaningful unsupported physical claim about them.


unsupported_physical_claim:
The plan claims a physical property that is not established by
medium/high-certainty Object DNA.

Examples:
- "non-slip" when no friction property exists
- "waterproof" without evidence
- "stable" when relevant stability is not grounded
- "reflective" without reflection evidence
- "diffuses light" without diffusion evidence


unsupported_capability:
The cited capability exists, but the plan stretches it beyond what the
capability actually means.

Example:
- cushion capability used to justify "non-slip"


hidden_assumption:
The plan depends on an unstated physical condition.

Examples:
- enough ambient light exists
- chair wheels lock
- an object fits inside another object
- the room contains a usable wall/table/window not listed


safety_or_uncertainty:
The plan ignores an Object DNA unknown_property or caution_note that is
material to the proposed use.


constraint_violation:
The plan conflicts with the user's stated constraints.


GROUNDING RULES

Only these physical resources are confirmed available:

Canonical inventory:
{json.dumps(inventory_payload, indent=2)}

Explicit external resources:
{json.dumps(external_resources, indent=2)}

Do NOT assume any other physical resource exists.


OBJECT DNA RULES

Object DNA is the ground truth for reusable physical capabilities.

Validated Object DNA:
{json.dumps(dna_payload, indent=2)}

Medium/high-certainty traits and affordances may support claims.

Low-certainty properties do NOT establish a physical claim.

Unknown properties remain unknown.

Caution notes remain active constraints.


IMPORTANT

Do not reject a plan merely because it is simple.

Do not require laboratory-grade proof for ordinary physical behavior.

Do reject specific physical adjectives or outcomes that exceed the evidence.


EXAMPLES

BAD:
"The blanket is non-slip."

If Object DNA only says:
- soft
- flexible
- cushion

then non-slip is unsupported.


BAD:
"This produces a well-lit shot."

If no available resource establishes illumination or usable ambient light,
that claim is unsupported.


BAD:
"Place the books on the tabletop."

If tabletop is not inventory or an external resource,
the plan is using an unlisted resource.


GOOD:
"Stack the books to elevate the phone."

If books contain:
- stack
- elevate

that claim is grounded.


USER GOAL:

{goal}


PLAN TO AUDIT:

{plan.model_dump_json(indent=2)}
""".strip(),
            }
        ],
        temperature=0,
        max_tokens=4000,
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        raise RuntimeError(
            "Semantic critic output was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            f"Semantic critic refused request: "
            f"{choice.message.refusal}"
        )

    raw_output = choice.message.content

    if not raw_output:
        raise RuntimeError(
            "Semantic critic returned no final content."
        )

    payload = load_model_json(
        raw_output
    )

    # Nemotron may use step_order=0 for findings that apply to the
    # overall plan instead of one specific numbered step.
    # ZERO represents those correctly as None / null.
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

    result = PlanCriticResult.model_validate(
        payload
    )

    # Do not trust the model's top-level passed flag blindly.
    # ZERO derives pass/fail from the actual findings.
    has_blocking_findings = any(
        finding.severity in {
            CriticSeverity.MEDIUM,
            CriticSeverity.HIGH,
        }
        for finding in result.findings
    )

    return result.model_copy(
        update={
            "passed": not has_blocking_findings,
        }
    )