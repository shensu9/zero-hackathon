import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from json_format_repair import (
    load_or_repair_json,
)
from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
    PlanRequirement,
)
from schemas import (
    InventoryItem,
)
from verification_gate_schemas import (
    VerificationGateAudit,
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


class RequirementRepairPayload(
    BaseModel,
):
    requirements: list[
        PlanRequirement
    ] = Field(
        min_length=1,
        max_length=5,
    )


def repair_verification_requirements(
    *,
    outcome: PlanOutcome,
    audit: VerificationGateAudit,
    inventory: list[InventoryItem],
    external_resources=None,
) -> list[PlanRequirement]:
    """
    Repair only CONDITIONAL requirements.

    The repair layer is explicitly grounded in the resources actually
    available to ZERO.

    It cannot alter the executable PhysicalPlan.
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
You are ZERO's verification-requirement repair layer.

A CONDITIONAL outcome has an executable physical plan that may happen
ONLY AFTER its requirements are satisfied.

The verification-gate auditor found problems.

Repair ONLY the requirements.

You may NOT modify the PhysicalPlan.


Return ONLY:

{{
  "requirements": [
    {{
      "requirement":
        "what must become known or true",

      "how_to_verify":
        "safe grounded verification before execution",

      "if_not_met":
        "what ZERO must do if verification fails"
    }}
  ]
}}


======================================================================
RESOURCE BOUNDARY
======================================================================

You may NOT invent a physical verification resource.

The only confirmed physical resources are:

- canonical inventory
- explicit external resources

Do NOT invent:

- pH strips
- test strips
- multimeters
- sensors
- rulers
- test kits
- additional containers
- measuring tools
- any other physical object that is not listed


Information-gathering may use:

- an existing label
- existing markings
- visual inspection
- asking the user
- a known specification
- documentation that is already available

If the required fact cannot be established with those methods,
if_not_met must say not to proceed.


======================================================================
UNKNOWN-SUBSTANCE SAFETY
======================================================================

If a substance is unidentified, do NOT use human exposure as a
verification method.

Never suggest:

- smelling or sniffing unknown substances
- tasting unknown substances
- touching unknown substances with bare skin
- inhaling vapors
- applying unknown substances to the body

Use only non-exposure information gathering such as:

- existing labels
- existing markings
- already-available documentation
- asking the user to identify the substance

If those methods cannot establish the required fact,
if_not_met must say not to proceed.


======================================================================
EXECUTION-GATE BOUNDARY
======================================================================

Verification must happen BEFORE the PhysicalPlan.

Verification must NOT:

- execute the gated physical action
- execute a smaller trial version of the gated action
- assume the unknown condition is already safe enough to test
- dispense, power, cut, attach, spray, pour, or otherwise perform
  the blocked use before authorization


BAD:

Requirement:
"Identify liquid before spraying."

how_to_verify:
"Spray a small test area."


GOOD:

Requirement:
"Identify liquid before spraying."

how_to_verify:
"Read existing label/markings or ask the user to identify the
contents without dispensing."

if_not_met:
"Do not spray."


======================================================================
OTHER HARD RULES
======================================================================

- Return the SAME NUMBER of requirements as the original outcome.

- Preserve each requirement's meaning.

- Do not weaken safety requirements.

- Do not change the executable PhysicalPlan.

- Do not add requirements unrelated to the audit findings.

- Return JSON only.


======================================================================
CANONICAL INVENTORY
======================================================================

{json.dumps(inventory_payload, indent=2)}


======================================================================
EXPLICIT EXTERNAL RESOURCES
======================================================================

{json.dumps(external_resources, indent=2)}


======================================================================
CURRENT REQUIREMENTS
======================================================================

{json.dumps(requirements_payload, indent=2)}


======================================================================
GATE-AUDIT FINDINGS
======================================================================

{json.dumps(findings_payload, indent=2)}


======================================================================
EXECUTABLE PLAN — MUST REMAIN UNCHANGED
======================================================================

{json.dumps(plan_payload, indent=2)}
""".strip(),
                }
            ],

            temperature=0,
            max_tokens=2500,
        )
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        raise RuntimeError(
            "Verification requirement repair "
            "was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            "Verification requirement repair refused: "
            f"{choice.message.refusal}"
        )

    raw_output = (
        choice.message.content
    )

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