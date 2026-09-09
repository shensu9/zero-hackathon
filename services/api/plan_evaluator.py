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

EVALUATOR_VERSION = "neutral_evaluator_v2"


# ---------------------------------------------------------------------------
# WORLD MODEL
# ---------------------------------------------------------------------------


def _build_compact_dna(
    object_dna: ObjectDNAResponse,
) -> list[dict]:
    """
    Build the neutral evaluator's compact physical world model.

    Low-certainty evidence is intentionally excluded.
    """

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
# NORMALIZATION
# ---------------------------------------------------------------------------


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

            # Some model responses use 0 to mean plan-level.
            if finding.get(
                "step_order"
            ) == 0:
                finding["step_order"] = None

    return payload


# ---------------------------------------------------------------------------
# DETERMINISTIC SCORING
# ---------------------------------------------------------------------------


def _derive_evaluation(
    evaluation: PlanEvaluation,
) -> PlanEvaluation:
    """
    Derive all benchmark metrics deterministically.

    The model identifies semantic findings only.
    It never controls acceptance or issue counts.
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
            if (
                finding.issue_type
                == issue_type
            )
        )

    return evaluation.model_copy(
        update={
            "medium_high_findings":
                medium_high_findings,

            "unlisted_resource_count":
                count_type(
                    CriticIssueType.UNLISTED_RESOURCE
                ),

            "unsupported_physical_claim_count":
                count_type(
                    CriticIssueType.UNSUPPORTED_PHYSICAL_CLAIM
                ),

            "unsupported_capability_count":
                count_type(
                    CriticIssueType.UNSUPPORTED_CAPABILITY
                ),

            "hidden_assumption_count":
                count_type(
                    CriticIssueType.HIDDEN_ASSUMPTION
                ),

            "safety_or_uncertainty_count":
                count_type(
                    CriticIssueType.SAFETY_OR_UNCERTAINTY
                ),

            "constraint_violation_count":
                count_type(
                    CriticIssueType.CONSTRAINT_VIOLATION
                ),

            "accepted":
                medium_high_findings == 0,
        }
    )


# ---------------------------------------------------------------------------
# NEUTRAL EVALUATOR
# ---------------------------------------------------------------------------


def evaluate_plan(
    *,
    plan: PhysicalPlan,
    goal: str,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
    external_resources: list[str] | None = None,
) -> PlanEvaluation:
    """
    Evaluate any physical plan against the same evidence.

    The evaluator is blind to whether a plan came from ZERO,
    a generic baseline, or a human-authored calibration case.
    """

    external_resources = (
        external_resources
        or []
    )

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

Evaluator version:
{EVALUATOR_VERSION}

You do NOT know how the supplied plan was generated.

Judge the plan only against:

1. the user's goal and constraints
2. canonical inventory
3. explicit external resources
4. validated physical traits and capabilities
5. explicit unknown properties
6. explicit safety cautions

Do not reward or penalize a plan because of its origin.

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

Do NOT return:
- scores
- counts
- accepted
- pass/fail

The application derives those deterministically.


======================================================================
CORE EVALUATION PRINCIPLE
======================================================================

Evaluate claims the plan ACTUALLY makes.

Do not strengthen a claim into a stronger one and then criticize
the stronger version.

Example:

Plan says:
"Place books on the blanket edge to help hold it down."

Do NOT rewrite this internally as:
"The books guarantee the blanket can never move."

Those are different claims.


======================================================================
ORDINARY PHYSICAL CONSEQUENCES ARE ALLOWED
======================================================================

Validated traits and capabilities may justify their ordinary,
non-extreme physical consequences.

Do NOT require laboratory measurements for ordinary physical use.

Examples:

If an object has:

provide_weight

then placing it on another lightweight/flexible object may ordinarily
be used to help hold that object down.

That does NOT prove:
- absolute immobilization
- guaranteed friction
- resistance to every disturbance

But ordinary wording such as:

"hold down the edge"
"help keep the edge in place"
"use as weight"

is allowed.

If an object has:

support

then it may ordinarily support an appropriate lightweight object
at rest.

That does NOT automatically prove:
- non-slip behavior
- fixed positioning
- vibration isolation
- resistance to disturbance

Only flag those stronger properties if the plan actually depends
on or claims them.

If an object is:

soft

or has:

cushion

then using it as a soft resting layer is ordinarily supported.

Do NOT require proof that the soft layer cannot slide unless:
- the goal requires it to remain fixed,
- the plan claims it is non-slip,
- or sliding materially defeats feasibility or safety.


======================================================================
MATERIALITY RULE
======================================================================

Do not search for every imaginable way a physical setup could fail.

A hidden assumption should be MEDIUM or HIGH only when the assumption
is materially necessary for:

- completing the requested goal,
- a central physical dependency,
- or safety.

Do NOT flag incidental possibilities that the plan does not depend on.

Examples of normally irrelevant concerns:

- an ordinary chair might be placed on a dirty floor
- a blanket resting on a seat might shift slightly
- books might be imperfectly aligned
- an object might move if deliberately disturbed

unless those conditions are central to the claimed outcome.


======================================================================
ACTIONS ARE NOT PHYSICAL RESOURCES
======================================================================

An action, observation, condition, or verification step is NOT itself
an unlisted physical resource.

Examples:

- inspect
- check
- verify
- compare
- confirm
- observe
- stop if unsafe
- use only if compatible

Do NOT classify these as unlisted_resource.

Only use unlisted_resource when the plan actually relies on a physical
thing that is absent from inventory and external resources.

Examples:

- tape
- lamp
- wall hook
- clamp
- ruler
- multimeter
- screwdriver
- table

If a plan explicitly says:

"measure with a multimeter"

and no multimeter exists, that can be an unlisted resource.

If a plan merely says:

"verify the electrical rating before use"

that is a conditional verification requirement, not an invented tool.


======================================================================
CONDITIONAL SAFETY PLANS
======================================================================

A plan may be valid even when an inventory property is unknown,
provided it preserves the uncertainty correctly.

Example:

The power strip has an unknown:
- electrical rating
- electrical condition

GOOD:

"Verify rating and condition before powered use.
Only proceed if both are suitable."

This preserves the uncertainty.

Do NOT reject such a plan merely because the property begins unknown.

BAD:

"Use the power strip immediately because it is assumed compatible."

That converts an unknown into an unsupported safety assumption.


======================================================================
CAPABILITY-SPECIFIC GUIDANCE
======================================================================

provide_weight

Supports:
- using the object as ordinary weight
- placing it on another object to help hold that object down

Does not guarantee:
- non-slip behavior
- complete immobilization
- anchoring under large force


provide_surface

Supports:
- providing a surface on which another appropriate object may rest

Does not automatically establish:
- perfect levelness
- non-slip behavior
- exact dimensions


support

Supports:
- bearing/resting support for an appropriate lightweight object

Does not automatically establish:
- fastening
- locking
- immobility under disturbance


elevate

Supports:
- raising an object relative to its previous resting level

Does not establish:
- exact height unless dimensions are known


stack

Supports:
- ordinary stacking

Do not automatically reject all stacks as unstable.

Only flag stability if:
- the plan makes an unusually strong stability claim,
- the configuration obviously depends on unsupported geometry,
- or safety materially depends on it.


cover

Supports:
- laying or draping the object over another surface/object

It does NOT by itself prove that an unsupported vertical backdrop
will remain suspended.

A vertical drape may still require a real support relationship.


cushion

Supports:
- a soft/cushioned resting layer

It does not establish:
- impact-proof
- non-slip
- waterproof


block_light

Supports:
- blocking light transmission

It does not establish:
- light diffusion
- reflectivity
- a visually dark photographic appearance
- neutral color


provide_power_connection

Supports:
- providing an electrical connection

If electrical rating or condition is unknown, powered use must remain
conditional on verification.

A plan that verifies first and proceeds only if suitable may be
accepted.


======================================================================
ISSUE TYPES
======================================================================


unlisted_resource

Use only when the plan physically depends on an actual object,
material, device, or tool that is not in inventory or explicit
external resources.

Do not use for abstract actions or verification conditions.


unsupported_physical_claim

The plan asserts a meaningful physical property or outcome that exceeds
the available evidence.

Examples:

- waterproof
- impact-proof
- non-slip
- guaranteed stable
- exact height without dimensions
- light diffusion without evidence


unsupported_capability

The plan uses an inventory object for a physical function that is not
reasonably supported by its validated traits/capabilities.

Example:

Using a spray bottle as a structural brace when no supporting capability
exists.


hidden_assumption

A materially necessary physical condition is not established and is
required for the plan to work or remain safe.

Do not use for incidental hypothetical failure modes.


safety_or_uncertainty

The plan improperly converts an explicitly unknown safety-relevant
property into an assumed known property, or ignores a relevant caution.


constraint_violation

The plan directly conflicts with the user's stated constraints.

Do not duplicate the same underlying issue as both an unsupported
capability and a constraint violation unless there are genuinely two
separate violations.


======================================================================
SEVERITY
======================================================================


LOW

Minor wording overclaim or uncertainty that does not materially
determine feasibility or safety.

LOW findings do not cause benchmark rejection.


MEDIUM

A meaningful unsupported dependency that could materially prevent the
requested goal from working.


HIGH

A major constraint violation, important safety problem, or unsupported
dependency central to the plan.


When uncertain whether an issue is LOW or MEDIUM, ask:

"If this assumption were false, would the requested plan materially
fail or become unsafe?"

If no, prefer LOW or no finding.


======================================================================
OUTPUT DISCIPLINE
======================================================================

- Maximum 12 findings.
- Prefer distinct issues.
- Do not duplicate the same underlying problem.
- Do not invent findings merely to be critical.
- Do not demand perfect physical certainty.
- Do not evaluate irrelevant environmental hypotheticals.
- claim: maximum about 18 words.
- explanation: maximum about 40 words.
- Use the real step number for step-specific findings.
- Use null for plan-wide findings.
- Never use step_order 0.


======================================================================
GROUNDING
======================================================================

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

    evaluation = (
        PlanEvaluation.model_validate(
            payload
        )
    )

    return _derive_evaluation(
        evaluation
    )