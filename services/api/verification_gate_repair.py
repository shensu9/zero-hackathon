import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from json_format_repair import load_or_repair_json
from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
    PlanRequirement,
)
from verification_gate_schemas import (
    VerificationGateAudit,
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


class RequirementRepairPayload(BaseModel):
    requirements: list[PlanRequirement] = Field(
        min_length=1,
        max_length=5,
    )


def repair_verification_requirements(
    *,
    outcome: PlanOutcome,
    audit: VerificationGateAudit,
) -> list[PlanRequirement]:
    """
    Repair only CONDITIONAL verification requirements.

    The executable PhysicalPlan is deliberately not returned by the
    model and therefore cannot be rewritten by this repair layer.
    """

    if (
        outcome.status
        != PlanOutcomeStatus.CONDITIONAL
    ):
        raise ValueError(
            "Verification-gate repair requires "
            "a CONDITIONAL outcome."
        )

    if outcome.plan is None:
        raise ValueError(
            "CONDITIONAL outcome contains no plan."
        )

    if audit.passed:
        return list(
            outcome.requirements
        )

    requirements_payload = [
        requirement.model_dump(
            mode="json"
        )
        for requirement
        in outcome.requirements
    ]

    findings_payload = [
        finding.model_dump(
            mode="json"
        )
        for finding
        in audit.findings
    ]

    plan_payload = (
        outcome.plan.model_dump(
            mode="json"
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
You are ZERO's verification-requirement repair layer.

A CONDITIONAL outcome has an executable physical plan that may happen
ONLY AFTER its requirements are satisfied.

The verification-gate auditor found problems in the requirements.

Repair ONLY the requirements.

You are NOT allowed to rewrite, redesign, add to, or remove anything
from the executable physical plan.

Return ONLY:

{{
  "requirements": [
    {{
      "requirement": "what must become known or true",
      "how_to_verify": "safe verification that happens before execution",
      "if_not_met": "what ZERO must do when verification fails"
    }}
  ]
}}


======================================================================
HARD RULES
======================================================================

- Return the SAME NUMBER of requirements as the original outcome.

- Preserve the original requirement meaning.

- Preserve the safety boundary.

- Repair how_to_verify when it improperly crosses the execution gate.

- Verification must happen BEFORE the physical plan.

- Verification must NOT perform the gated action.

- Verification must NOT perform a smaller trial version of the
  gated action.

- Verification must NOT assume that the unknown condition is already
  safe enough to test.

- Do not invent physical tools, devices, materials, or resources.

- Information-gathering may include:
  reading an existing label,
  visually inspecting existing markings,
  checking already-available documentation,
  asking the user,
  confirming a known specification,
  identifying contents without dispensing them.

- If the required fact cannot be established without crossing the
  gate, if_not_met must clearly say not to proceed.

- Do not weaken a safety requirement merely to make the plan executable.

- Return JSON only.


======================================================================
EXAMPLE
======================================================================

BAD:

requirement:
"Identify unknown liquid before spraying."

how_to_verify:
"Spray a small test area first."

GOOD:

requirement:
"Identify unknown liquid before spraying."

how_to_verify:
"Read an existing label or otherwise establish the contents without
dispensing the liquid."

if_not_met:
"Do not spray."


======================================================================
CURRENT REQUIREMENTS
======================================================================

{json.dumps(requirements_payload, indent=2)}


======================================================================
GATE-AUDIT FINDINGS
======================================================================

{json.dumps(findings_payload, indent=2)}


======================================================================
EXECUTABLE PLAN THAT MUST REMAIN UNCHANGED
======================================================================

{json.dumps(plan_payload, indent=2)}
""".strip(),
            }
        ],

        temperature=0,
        max_tokens=2500,
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        raise RuntimeError(
            "Verification requirement repair was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            "Verification requirement repair refused: "
            f"{choice.message.refusal}"
        )

    raw_output = choice.message.content

    if not raw_output:
        raise RuntimeError(
            "Verification requirement repair returned "
            "no final content."
        )

    payload = load_or_repair_json(
        raw_output
    )

    repaired = (
        RequirementRepairPayload.model_validate(
            payload
        )
    )

    if (
        len(repaired.requirements)
        != len(outcome.requirements)
    ):
        raise RuntimeError(
            "Verification requirement repair changed "
            "the number of requirements."
        )

    return repaired.requirements