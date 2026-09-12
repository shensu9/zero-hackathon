import json
import os
from json import JSONDecodeError

from dotenv import load_dotenv
from openai import OpenAI

from critic_schemas import (
    CriticSeverity,
    PlanCriticResult,
)
from model_json import load_model_json
from plan_schemas import PhysicalPlan
from schemas import (
    CertaintyLevel,
    InventoryItem,
    ObjectDNAResponse,
)


load_dotenv()

api_key = os.getenv(
    "NEBIUS_API_KEY"
)

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


MODEL = (
    "nvidia/nemotron-3-super-120b-a12b"
)


def _build_compact_dna(
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
                    for trait
                    in dna.physical_traits
                    if trait.certainty
                    != CertaintyLevel.LOW
                ],

                "capabilities": [
                    affordance.capability.value
                    for affordance
                    in dna.affordances
                    if affordance.certainty
                    != CertaintyLevel.LOW
                ],

                "unknown_properties":
                    dna.unknown_properties,

                "caution_notes":
                    dna.caution_notes,
            }
        )

    return result


def _normalize_critic_payload(
    payload: dict,
) -> dict:
    findings = payload.get(
        "findings",
        [],
    )

    if isinstance(
        findings,
        list,
    ):
        for finding in findings:
            if not isinstance(
                finding,
                dict,
            ):
                continue

            # Nemotron occasionally uses 0 to mean "plan-level".
            if finding.get(
                "step_order"
            ) == 0:
                finding[
                    "step_order"
                ] = None

    return payload


def _repair_malformed_critic_json(
    raw_output: str,
) -> dict:
    """
    Repair formatting only.

    This call is not allowed to invent, remove, or reinterpret critic
    findings. It only converts malformed model output into valid JSON.
    """

    response = (
        client.chat.completions.create(
            model=MODEL,
            reasoning_effort="low",

            response_format={
                "type":
                    "json_object"
            },

            messages=[
                {
                    "role":
                        "user",

                    "content":
                        f"""
You are a JSON formatting repair tool.

The following text was intended to be ZERO semantic-critic JSON,
but it is malformed.

Convert it into valid JSON with EXACTLY this structure:

{{
  "passed": false,
  "findings": [
    {{
      "step_order": 1,
      "claim": "short claim",
      "issue_type": "unlisted_resource | unsupported_physical_claim | unsupported_capability | hidden_assumption | safety_or_uncertainty | constraint_violation",
      "severity": "low | medium | high",
      "explanation": "brief explanation",
      "recommended_fix": "brief fix"
    }}
  ]
}}

Rules:

- Preserve the original findings and meaning.
- Do NOT invent new findings.
- Do NOT remove findings.
- Do NOT change severity unless required to recover malformed syntax.
- Use null for plan-level step_order.
- Never use step_order 0.
- Return JSON only.

Malformed input:

{raw_output}
""".strip(),
                }
            ],

            temperature=0,
            max_tokens=2500,
        )
    )

    choice = response.choices[0]

    if (
        choice.finish_reason
        == "length"
    ):
        raise RuntimeError(
            "Critic JSON-repair output was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            "Critic JSON repair refused request: "
            f"{choice.message.refusal}"
        )

    repaired_output = (
        choice.message.content
    )

    if not repaired_output:
        raise RuntimeError(
            "Critic JSON repair returned no output."
        )

    return load_model_json(
        repaired_output
    )


def _parse_critic_output(
    raw_output: str,
) -> PlanCriticResult:
    """
    Parse normal critic JSON.

    If the model produced malformed JSON, make one tightly constrained
    formatting-repair attempt rather than rerunning the whole ZERO pipeline.
    """

    try:
        payload = load_model_json(
            raw_output
        )

    except JSONDecodeError:
        print(
            "Semantic critic returned malformed JSON; "
            "attempting one formatting repair..."
        )

        payload = (
            _repair_malformed_critic_json(
                raw_output
            )
        )

    payload = (
        _normalize_critic_payload(
            payload
        )
    )

    result = (
        PlanCriticResult.model_validate(
            payload
        )
    )

    has_blocking_findings = any(
        finding.severity
        in {
            CriticSeverity.MEDIUM,
            CriticSeverity.HIGH,
        }
        for finding
        in result.findings
    )

    return result.model_copy(
        update={
            "passed":
                not has_blocking_findings,
        }
    )


def _build_semantic_critic_prompt(
    *,
    plan: PhysicalPlan,
    goal: str,
    inventory_payload: list[dict],
    compact_dna: list[dict],
    external_resources: list[str],
) -> str:
    """
    Build ZERO's semantic physical-plan audit prompt.

    The critic must perform an exhaustive field-by-field sweep before it
    decides whether the plan passes. This avoids a model finding one issue
    and then overlooking a separate unsupported claim elsewhere in the plan.
    """

    return f"""
You are ZERO's semantic physical-plan critic.

The plan has ALREADY passed deterministic validation:

- every inventory item ID exists
- every physical item use cites a capability
- every cited capability exists in validated Object DNA

Do NOT repeat those checks unless the language stretches a capability
beyond its actual meaning.

Your job is to detect unsupported physical claims that remain in the
plan's natural language.


======================================================================
FULL-PLAN COVERAGE CONTRACT
======================================================================

Before deciding whether the plan passes, perform a COMPLETE field-by-field
semantic sweep of the entire PhysicalPlan.

Internally inspect ALL of these locations:

1. title
2. summary
3. EVERY step.action
4. EVERY capability_uses[].purpose in EVERY step
5. EVERY step.why_it_helps
6. EVERY assumption
7. EVERY unresolved_risk
8. EVERY constraint_check entry

Do NOT stop auditing after finding the first problem.

Finding one unsupported claim does not excuse overlooking another one.

Treat each materially different physical property, physical outcome,
causal effect, resource dependency, safety claim, or required condition
as a separate claim that must be grounded.

A field is not automatically safe merely because it sounds descriptive,
helpful, cautious, or appears in why_it_helps, summary, assumptions,
risks, or constraint_check.

Before returning passed=true, complete the entire sweep above and verify
that NO meaningful unsupported physical claim remains in ANY listed field.

The output may contain at most 8 findings. If more than 8 issues exist,
return the most important 8, but passed must still be false.


======================================================================
APPEARANCE / QUALITY CLAIMS
======================================================================

Capabilities such as:

- cover
- hang
- support
- provide_surface
- fasten

establish only their direct physical meanings.

They do NOT automatically establish visual or quality properties such as:

- clean
- uniform
- plain
- seamless
- wrinkle-free
- smooth
- consistent color
- consistent texture
- professional-looking
- visually neutral

For example:

A blanket that can "cover" or "hang" may be usable as a backdrop.

That alone does NOT prove:

"Provides a uniform background."

It also does NOT prove:

"Provides a clean background."

It also does NOT prove:

"Provides a consistent color or texture."

Those appearance claims require supporting observed description,
validated traits, capabilities, or explicitly confirmed information.

Do NOT use these words as a blind blacklist.

If the evidence genuinely establishes the property, the claim may be
grounded.

Reject only when the specific claim exceeds the available evidence.


======================================================================
CAUSAL / CERTAINTY CLAIMS
======================================================================

A direct capability does not automatically prove its hoped-for downstream
effect.

Examples:

"fasten" does not by itself prove:
- prevents slipping
- reduces slip risk
- guarantees stability
- ensures an object stays in place
- makes an arrangement safe

"diffuse_light" does not by itself prove:
- enough light for exposure
- well-lit result
- correct exposure
- professional-quality lighting

"provide_surface" does not by itself prove:
- arbitrary product fits
- load capacity is sufficient
- surface is clean
- surface is stable under an unknown load

Audit causal words and certainty words carefully, including phrases such
as:

- prevents
- reduces
- ensures
- guarantees
- keeps stable
- makes safe
- sufficient
- adequate
- comfortably fits
- professional-quality

Again, these are not automatic violations. They require grounding.


======================================================================
RETURN FORMAT
======================================================================

Return ONLY valid JSON:

{{
  "passed": false,
  "findings": [
    {{
      "step_order": 1,
      "claim": "short problematic claim",
      "issue_type": "unlisted_resource | unsupported_physical_claim | unsupported_capability | hidden_assumption | safety_or_uncertainty | constraint_violation",
      "severity": "low | medium | high",
      "explanation": "brief explanation",
      "recommended_fix": "brief specific fix"
    }}
  ]
}}


OUTPUT LIMITS

- Maximum 8 findings.
- Prefer MEDIUM/HIGH issues.
- Include LOW issues only when materially useful.
- claim: maximum about 15 words.
- explanation: maximum about 35 words.
- recommended_fix: maximum about 30 words.
- Do not duplicate the same issue at plan level and step level unless
  both are genuinely useful.


STEP ORDER RULE

- Use the real step number for a step-specific issue.
- Use null for title, summary, assumptions, risks, constraint checks,
  or plan-wide issues.
- Never use 0.


PASS RULE

passed should be true only when:

1. the FULL-PLAN COVERAGE CONTRACT has been completed, AND
2. no meaningful unsupported physical claim remains anywhere in the plan.

Do not return passed=true merely because one previously known finding
has been fixed.

Do not invent findings merely to be critical.


ISSUE TYPES

unlisted_resource:
The plan relies on a physical resource that is not in canonical
inventory or explicit external resources.

Examples:
- tabletop
- lamp
- window
- tape
- tripod
- shelf


unsupported_physical_claim:
The plan states a physical property or outcome not established by
validated traits/capabilities.

Examples:
- non-slip
- waterproof
- reflective
- stable
- well-lit
- minimal shadow
- sufficient illumination
- clean surface
- uniform background
- consistent color or texture


unsupported_capability:
A real capability is stretched beyond what it means.

Example:
Using "cushion" to justify "non-slip."


hidden_assumption:
The plan requires an unstated or unverified physical condition.

Examples:
- enough ambient illumination
- chair wheels lock
- object fits into another object
- product fits on a surface of unknown size
- unknown load-bearing capacity is sufficient
- unlisted furniture or mounting point exists


safety_or_uncertainty:
The plan ignores an unknown_property or caution_note that matters
to the proposed use.


constraint_violation:
The plan conflicts with the user's stated constraints.


GROUNDING

Available inventory:

{json.dumps(
    inventory_payload,
    indent=2,
)}

Explicit external resources:

{json.dumps(
    external_resources,
    indent=2,
)}

No other physical resources are confirmed.


VALIDATED COMPACT OBJECT DNA

{json.dumps(
    compact_dna,
    indent=2,
)}


GROUNDING RULES

- Medium/high traits and capabilities may support claims.
- Low-certainty properties do not establish claims.
- Unknown properties remain unknown.
- Caution notes remain active.
- Object names alone do not establish extra physical properties.
- Generic category expectations do not override explicit unknowns.
- Do not require laboratory-level certainty for ordinary physical use.
- Do reject specific claims that exceed the available evidence.
- A capability supports its direct affordance, not every desirable
  consequence that might follow from using it.


EXAMPLES

BAD:

"The blanket is non-slip."

If Object DNA only provides:
- soft
- flexible
- cushion

then non-slip is unsupported.


BAD:

"The blanket provides a uniform background."

If Object DNA establishes only capabilities such as:
- cover
- hang

but does not establish uniform color or texture,
then uniform background is unsupported.


BAD:

"The blanket provides a clean background."

If cleanliness is not observed, validated, or confirmed,
then clean background is unsupported.


BAD:

"This produces a well-lit image."

If the available lighting evidence does not establish sufficient
illumination for exposure, the statement is unsupported.


BAD:

"Place the books on the tabletop."

If no tabletop exists in inventory or external resources,
that is an unlisted resource.


GOOD:

"Stack the books to elevate the phone."

If books have:
- stack
- elevate

that direct claim is grounded.


GOOD:

"Use the blanket as a backdrop."

If the blanket has:
- cover
or
- hang

that direct use may be grounded without claiming unsupported
uniformity, cleanliness, color, texture, or image quality.


USER GOAL

{goal}


PLAN TO AUDIT

{plan.model_dump_json(
    indent=2
)}
""".strip()


def audit_plan_semantics(
    *,
    plan: PhysicalPlan,
    goal: str,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
    external_resources: list[str] | None = None,
) -> PlanCriticResult:
    external_resources = (
        external_resources
        or []
    )

    inventory_payload = [
        {
            "id": item.id,
            "name": item.name,
            "description":
                item.description,
        }
        for item
        in inventory
    ]

    compact_dna = (
        _build_compact_dna(
            object_dna
        )
    )

    prompt = (
        _build_semantic_critic_prompt(
            plan=plan,
            goal=goal,
            inventory_payload=(
                inventory_payload
            ),
            compact_dna=(
                compact_dna
            ),
            external_resources=(
                external_resources
            ),
        )
    )

    response = (
        client.chat.completions.create(
            model=MODEL,
            reasoning_effort="low",

            response_format={
                "type":
                    "json_object"
            },

            messages=[
                {
                    "role":
                        "user",

                    "content":
                        prompt,
                }
            ],

            temperature=0,
            max_tokens=4500,
        )
    )

    choice = response.choices[0]

    if (
        choice.finish_reason
        == "length"
    ):
        raise RuntimeError(
            "Semantic critic output was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            "Semantic critic refused request: "
            f"{choice.message.refusal}"
        )

    raw_output = (
        choice.message.content
    )

    if not raw_output:
        raise RuntimeError(
            "Semantic critic returned no final content."
        )

    return _parse_critic_output(
        raw_output
    )