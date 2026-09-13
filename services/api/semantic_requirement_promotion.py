import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from critic_schemas import (
    CriticIssueType,
    CriticSeverity,
    PlanCriticResult,
)
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

MAX_TOTAL_REQUIREMENTS = 5


PROMOTABLE_ISSUE_TYPES = frozenset(
    {
        CriticIssueType.UNSUPPORTED_PHYSICAL_CLAIM,
        CriticIssueType.HIDDEN_ASSUMPTION,
        CriticIssueType.SAFETY_OR_UNCERTAINTY,
    }
)


BLOCKING_SEVERITIES = frozenset(
    {
        CriticSeverity.MEDIUM,
        CriticSeverity.HIGH,
    }
)


class RequirementPromotionPayload(
    BaseModel
):
    requirements: list[
        PlanRequirement
    ] = Field(
        min_length=1,
        max_length=MAX_TOTAL_REQUIREMENTS,
    )


def _blocking_findings(
    critic: PlanCriticResult,
):
    return [
        finding
        for finding
        in critic.findings
        if (
            finding.severity
            in BLOCKING_SEVERITIES
        )
    ]


def promotion_ineligibility_reason(
    *,
    outcome: PlanOutcome,
    critic: PlanCriticResult,
) -> str | None:
    """
    Return None only when the remaining semantic failure is
    eligible for ONE bounded conversion into pre-execution
    verification requirements.

    This function is intentionally fail-closed.
    """

    if (
        outcome.status
        != PlanOutcomeStatus.CONDITIONAL
    ):
        return (
            "Semantic requirement promotion is allowed "
            "only for an already-CONDITIONAL outcome."
        )

    if outcome.plan is None:
        return (
            "CONDITIONAL outcome contains no PhysicalPlan."
        )

    blocking = (
        _blocking_findings(
            critic
        )
    )

    if not blocking:
        return (
            "No MEDIUM/HIGH semantic findings remain."
        )

    if any(
        finding.severity
        == CriticSeverity.HIGH
        for finding
        in blocking
    ):
        return (
            "HIGH-severity semantic findings may not be "
            "converted into verification requirements."
        )

    non_promotable = [
        finding
        for finding
        in blocking
        if (
            finding.issue_type
            not in PROMOTABLE_ISSUE_TYPES
        )
    ]

    if non_promotable:
        issue_types = sorted(
            {
                finding.issue_type.value
                for finding
                in non_promotable
            }
        )

        return (
            "Semantic findings contain non-promotable "
            "issue types: "
            + ", ".join(
                issue_types
            )
        )

    if (
        len(outcome.requirements)
        >= MAX_TOTAL_REQUIREMENTS
    ):
        return (
            "No PlanRequirement capacity remains."
        )

    return None


def semantic_findings_are_promotable(
    *,
    outcome: PlanOutcome,
    critic: PlanCriticResult,
) -> bool:
    return (
        promotion_ineligibility_reason(
            outcome=outcome,
            critic=critic,
        )
        is None
    )


def _normalized_text(
    value: str,
) -> str:
    return " ".join(
        value
        .strip()
        .lower()
        .split()
    )


def _validate_promoted_requirements(
    *,
    outcome: PlanOutcome,
    promoted_requirements: list[
        PlanRequirement
    ],
) -> list[PlanRequirement]:
    """
    Deterministic post-model boundary.

    Existing requirements are immutable here. The model may
    return only NEW requirements.
    """

    available_slots = (
        MAX_TOTAL_REQUIREMENTS
        - len(
            outcome.requirements
        )
    )

    if available_slots <= 0:
        raise RuntimeError(
            "No PlanRequirement capacity remains."
        )

    if not promoted_requirements:
        raise RuntimeError(
            "Requirement promotion returned no requirements."
        )

    if (
        len(promoted_requirements)
        > available_slots
    ):
        raise RuntimeError(
            "Requirement promotion exceeded remaining "
            "PlanRequirement capacity."
        )

    existing_keys = {
        _normalized_text(
            requirement.requirement
        )
        for requirement
        in outcome.requirements
    }

    new_keys: set[str] = set()

    for requirement in promoted_requirements:
        key = _normalized_text(
            requirement.requirement
        )

        if key in existing_keys:
            raise RuntimeError(
                "Requirement promotion duplicated an "
                "existing requirement."
            )

        if key in new_keys:
            raise RuntimeError(
                "Requirement promotion returned duplicate "
                "new requirements."
            )

        new_keys.add(
            key
        )

    return list(
        promoted_requirements
    )


def promote_semantic_findings_to_requirements(
    *,
    outcome: PlanOutcome,
    critic: PlanCriticResult,
    goal: str,
    inventory: list[
        InventoryItem
    ],
    external_resources=None,
) -> list[PlanRequirement]:
    """
    ONE bounded semantic-finding promotion attempt.

    This layer:
    - never changes the PhysicalPlan
    - never removes or rewrites existing requirements
    - may return only NEW PlanRequirement objects
    - may run only for an already-CONDITIONAL outcome
    - rejects HIGH-severity or structurally invalid failures

    Verification-gate auditing remains authoritative after
    this stage.
    """

    reason = (
        promotion_ineligibility_reason(
            outcome=outcome,
            critic=critic,
        )
    )

    if reason is not None:
        raise ValueError(
            "Semantic findings are not eligible for "
            "requirement promotion: "
            f"{reason}"
        )

    external_resources = list(
        external_resources
        or []
    )

    blocking = (
        _blocking_findings(
            critic
        )
    )

    available_slots = (
        MAX_TOTAL_REQUIREMENTS
        - len(
            outcome.requirements
        )
    )

    findings_payload = [
        finding.model_dump(
            mode="json"
        )
        for finding
        in blocking
    ]

    existing_requirements_payload = [
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

    inventory_payload = [
        item.model_dump(
            mode="json"
        )
        for item
        in inventory
    ]

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
You are ZERO's semantic-uncertainty to verification-requirement
promotion layer.

ZERO has already exhausted its bounded PhysicalPlan repair budget.

The PhysicalPlan MUST NOT be modified again.

The remaining semantic findings have already passed ZERO's strict
deterministic eligibility rule:

- every blocking finding is MEDIUM severity
- every blocking finding is one of:
  unsupported_physical_claim
  hidden_assumption
  safety_or_uncertainty
- the PlanOutcome is already CONDITIONAL
- HIGH-severity findings are never promotable
- unsupported capabilities, unlisted resources, and constraint
  violations are never promotable

Your job is ONLY to identify whether multiple provided findings depend
on one or more unresolved physical facts that can become explicit
pre-execution PlanRequirement objects.

Return ONLY NEW requirements.

Do NOT repeat, rewrite, remove, or weaken existing requirements.

The existing PhysicalPlan remains frozen.

======================================================================
OUTPUT
======================================================================

Return JSON only:

{{
  "requirements": [
    {{
      "requirement":
        "what physical fact must be verified true before execution",

      "how_to_verify":
        "safe grounded verification that happens before the plan",

      "if_not_met":
        "what ZERO must do if the requirement is not satisfied"
    }}
  ]
}}

======================================================================
PROMOTION RULES
======================================================================

- Return at least 1 new requirement.
- Return at most {available_slots} new requirement(s).
- Deduplicate findings that depend on the SAME unresolved physical fact.
- One requirement may cover several semantic findings.
- Do not create one requirement per finding unless they genuinely
  represent different unresolved facts.
- Do not alter the PhysicalPlan.
- Do not claim an unknown fact is already true.
- Do not invent capabilities.
- Do not invent physical tools, materials, or resources.
- Use only:
  * facts the user can safely inspect or confirm before execution,
  * inventory that is actually listed below,
  * listed external resources.
- Verification must happen BEFORE the PhysicalPlan begins.
- Verification must not perform the gated action.
- Verification must not perform a smaller trial version of the gated
  action merely to see whether it works.
- Verification must not assume the unknown condition is already safe.
- If a required physical fact is not true, if_not_met must stop that
  execution path or require an alternative rather than proceeding on
  assumption.
- Keep each requirement narrowly tied to the supplied semantic findings.
- Do not add unrelated safety advice.
- Do not duplicate an existing requirement.

======================================================================
GOAL
======================================================================

{goal}

======================================================================
CURRENT CONDITIONAL OUTCOME EXPLANATION
======================================================================

{outcome.explanation}

======================================================================
EXISTING REQUIREMENTS ??PRESERVE EXACTLY
======================================================================

{json.dumps(existing_requirements_payload, indent=2)}

======================================================================
BLOCKING SEMANTIC FINDINGS TO PROMOTE
======================================================================

{json.dumps(findings_payload, indent=2)}

======================================================================
FROZEN PHYSICAL PLAN
======================================================================

{json.dumps(plan_payload, indent=2)}

======================================================================
AVAILABLE INVENTORY
======================================================================

{json.dumps(inventory_payload, indent=2)}

======================================================================
AVAILABLE EXTERNAL RESOURCES
======================================================================

{json.dumps(external_resources, indent=2)}
""".strip(),
                }
            ],
        )
    )

    choice = response.choices[0]

    if (
        choice.finish_reason
        == "length"
    ):
        raise RuntimeError(
            "Semantic requirement promotion was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            "Semantic requirement promotion refused: "
            f"{choice.message.refusal}"
        )

    raw_output = (
        choice.message.content
    )

    if not raw_output:
        raise RuntimeError(
            "Semantic requirement promotion returned "
            "no final content."
        )

    payload = (
        load_or_repair_json(
            raw_output
        )
    )

    promoted = (
        RequirementPromotionPayload
        .model_validate(
            payload
        )
    )

    return (
        _validate_promoted_requirements(
            outcome=outcome,
            promoted_requirements=(
                promoted.requirements
            ),
        )
    )
