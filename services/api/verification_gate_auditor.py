import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from json_format_repair import (
    load_or_repair_json,
)
from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
)
from verification_gate_schemas import (
    VerificationGateAudit,
    VerificationGateSeverity,
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


def _derive_passed(
    audit: VerificationGateAudit,
) -> VerificationGateAudit:
    """
    Derive pass/fail deterministically.

    The model identifies semantic findings.
    It does not control whether the gate passes.
    """

    blocking = any(
        finding.severity
        in {
            VerificationGateSeverity.MEDIUM,
            VerificationGateSeverity.HIGH,
        }
        for finding
        in audit.findings
    )

    return audit.model_copy(
        update={
            "passed": not blocking,
        }
    )


def audit_verification_gates(
    outcome: PlanOutcome,
) -> VerificationGateAudit:
    """
    Audit CONDITIONAL requirements.

    A verification step must not execute the physical action that
    the requirement is supposed to gate.

    Non-CONDITIONAL outcomes have no executable conditional gate
    to audit and therefore pass automatically.
    """

    if (
        outcome.status
        != PlanOutcomeStatus.CONDITIONAL
    ):
        return VerificationGateAudit(
            passed=True,
            findings=[],
        )

    if outcome.plan is None:
        raise RuntimeError(
            "CONDITIONAL outcome unexpectedly "
            "contains no plan."
        )

    requirements_payload = [
        requirement.model_dump(
            mode="json"
        )
        for requirement
        in outcome.requirements
    ]

    plan_payload = (
        outcome.plan.model_dump(
            mode="json"
        )
    )

    response = (
        client.chat.completions.create(
            model=MODEL,
            reasoning_effort="low",

            response_format={
                "type": "json_object"
            },

            messages=[
                {
                    "role": "user",
                    "content": f"""
You are ZERO's verification-gate auditor.

You are auditing a CONDITIONAL physical plan.

The plan may execute ONLY AFTER its requirements have been
satisfied.

Your job is to detect whether any requirement's "how_to_verify"
method improperly performs, partially performs, or assumes the
physical action that the requirement is supposed to gate.


Return ONLY valid JSON:

{{
  "passed": false,

  "findings": [
    {{
      "requirement_index": 0,

      "issue_type":
        "executes_gated_action | assumes_requirement_met | unsafe_verification | not_actually_verifiable",

      "severity":
        "low | medium | high",

      "claim":
        "short problematic verification claim",

      "explanation":
        "brief explanation",

      "recommended_fix":
        "brief safer verification approach"
    }}
  ]
}}


======================================================================
CORE RULE
======================================================================

Verification must happen BEFORE the gated executable action.

A verification method must NOT perform the gated action merely to
discover whether the gated action is safe or appropriate.


Example:

Requirement:
"Liquid contents must be identified as appropriate before spraying."

BAD verification:
"Spray a small test area to see whether the liquid is suitable."

Why bad:
The verification performs spraying before spraying has been
authorized.


GOOD verification:
"Read the bottle label or otherwise identify the product/contents
without dispensing it."

Why good:
The prerequisite is resolved without executing the gated action.


======================================================================
WHAT COUNTS AS EXECUTING THE GATED ACTION
======================================================================

Flag when how_to_verify:

- performs the same physical action as the conditional plan
- performs a smaller trial version of that physical action
- consumes, dispenses, powers, cuts, damages, attaches, applies,
  sprays, pours, or otherwise uses the resource in the blocked way
- assumes the unknown property is already safe enough to test


Examples:

BAD:
"Plug it in briefly to verify whether the electrical device is safe."

BAD:
"Spray a little liquid first to determine whether spraying is safe."

BAD:
"Cut a small section first to verify that cutting is acceptable."


======================================================================
WHAT IS ALLOWED
======================================================================

Verification may use information-gathering that does NOT execute the
blocked action.

Examples:

- read a label
- inspect visible markings
- ask the user
- confirm a known specification
- check documentation already available
- visually inspect condition
- identify contents without dispensing
- stop if the required fact cannot be established


Do NOT invent a physical tool.

If verification explicitly requires an unavailable tool or device,
flag not_actually_verifiable.


======================================================================
ISSUE TYPES
======================================================================


executes_gated_action

The verification performs or partially performs the action that should
remain blocked until after verification.


assumes_requirement_met

The verification method relies on the very unknown condition it is
supposed to establish.


unsafe_verification

The verification introduces a meaningful safety risk before the
requirement has been resolved.


not_actually_verifiable

The proposed verification cannot be carried out as described without
an unavailable resource or missing information.


======================================================================
SEVERITY
======================================================================

LOW:
Minor wording ambiguity with no meaningful safety or sequencing impact.

MEDIUM:
Verification meaningfully crosses the gate or depends on an unsupported
condition.

HIGH:
Verification performs a safety-critical blocked action or defeats the
purpose of the requirement entirely.


======================================================================
OUTPUT RULES
======================================================================

- Maximum 10 findings.
- Do not invent issues merely to be critical.
- Do not criticize the executable plan itself unless necessary to
  determine whether verification crosses the gate.
- requirement_index is zero-based.
- Use the real requirement index.
- Keep findings concise.
- Return JSON only.


======================================================================
CONDITIONAL REQUIREMENTS
======================================================================

{json.dumps(requirements_payload, indent=2)}


======================================================================
EXECUTABLE PLAN AFTER REQUIREMENTS PASS
======================================================================

{json.dumps(plan_payload, indent=2)}
""".strip(),
                }
            ],

            temperature=0,
            max_tokens=3000,
        )
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        raise RuntimeError(
            "Verification gate audit was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            "Verification gate audit refused: "
            f"{choice.message.refusal}"
        )

    raw_output = (
        choice.message.content
    )

    if not raw_output:
        raise RuntimeError(
            "Verification gate audit returned "
            "no final content."
        )

    payload = load_or_repair_json(
        raw_output
    )

    audit = (
        VerificationGateAudit.model_validate(
            payload
        )
    )

    return _derive_passed(
        audit
    )