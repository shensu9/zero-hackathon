import json

from critic_schemas import (
    CriticSeverity,
    PlanCriticResult,
)
from model_json import load_model_json
from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
)
from schemas import (
    InventoryItem,
    ObjectDNAResponse,
)
import semantic_critic


def _build_confirmation_field_map(
    outcome: PlanOutcome,
) -> dict[str, str]:
    """
    Exact semantic fields that must be audited for a
    NEEDS_CONFIRMATION outcome.
    """

    if (
        outcome.status
        != PlanOutcomeStatus.NEEDS_CONFIRMATION
    ):
        raise ValueError(
            "Confirmation semantic audit requires "
            "NEEDS_CONFIRMATION."
        )

    fields = {
        "explanation":
            outcome.explanation,
    }

    for index, requirement in enumerate(
        outcome.requirements,
        start=1,
    ):
        prefix = (
            f"requirement:{index}"
        )

        fields[
            f"{prefix}:requirement"
        ] = requirement.requirement

        fields[
            f"{prefix}:how_to_verify"
        ] = requirement.how_to_verify

        fields[
            f"{prefix}:if_not_met"
        ] = requirement.if_not_met

    return fields


def _build_confirmation_critic_prompt(
    *,
    outcome: PlanOutcome,
    goal: str,
    inventory_payload: list[dict],
    compact_dna: list[dict],
    external_resources: list[str],
    field_map: dict[str, str],
) -> str:
    """
    Build the closed-world semantic audit for
    NEEDS_CONFIRMATION.
    """

    return f"""
You are ZERO's NEEDS_CONFIRMATION grounding critic.

ZERO has returned NEEDS_CONFIRMATION rather than an executable
PhysicalPlan.

Your job is NOT to invent a plan and NOT to answer the missing
question for the user.

Your job is to determine whether NEEDS_CONFIRMATION is actually
justified by the CURRENT grounded world model and the user's goal.

STATUS BOUNDARY:

NEEDS_CONFIRMATION is correct only when:

- some information, fact, identity, preference, or choice is genuinely
  missing,
- that missing information materially determines WHICH physical plan
  ZERO should select,
- ZERO cannot responsibly choose the plan until that information is
  resolved,
- and the missing information is not already established by the goal,
  active inventory, validated Object DNA, or external resources.

IMPORTANT DISTINCTIONS:

1. SOLVED

If a grounded executable plan can already be selected and executed now,
NEEDS_CONFIRMATION is too conservative.

2. CONDITIONAL

If ZERO already knows WHICH physical plan should be executed, but a
concrete property or safety condition must merely be verified before
execution, that is CONDITIONAL, not NEEDS_CONFIRMATION.

Examples:
- verify load-bearing capacity before executing an already-selected plan
- verify electrical compatibility before powering an already-selected
  device
- verify liquid contents before using an already-selected dispenser

Those checks affect WHETHER an already-selected plan may execute.
They do not determine WHICH plan should be selected.

3. CANNOT_SAFELY_SOLVE

If no confirmation could produce a grounded, constraint-compatible safe
solution with the current resources, NEEDS_CONFIRMATION is not justified.
The correct boundary may instead be CANNOT_SAFELY_SOLVE.

4. NEEDS_CONFIRMATION

Use NEEDS_CONFIRMATION when resolving the missing information actually
selects among materially different physical plans or targets.

Examples:
- the user must choose which of two different objects they intend to
  display, protect, move, or prioritize
- the goal refers to an unidentified target whose identity determines
  what physical action is appropriate
- a missing user preference materially changes the selected physical
  arrangement

GROUNDING RULES:

- Treat inventory and Object DNA as the current grounded world.
- Do not invent capabilities, resources, user preferences, identities,
  dimensions, attachment methods, or safety properties.
- Do not ask the user to confirm information that is already grounded.
- Do not manufacture ambiguity merely because several valid plans happen
  to exist. If any grounded plan satisfies the goal without needing a
  missing user-specific criterion, NEEDS_CONFIRMATION may be unjustified.
- The missing information must materially affect plan selection.
- A requirement that only verifies whether an already-known plan is safe
  belongs under CONDITIONAL.
- Requirements must not disguise an executable physical step as a
  confirmation question.
- Respect all user constraints exactly.
- Do not use unavailable external resources.

AUDIT EVERY REQUIREMENT FIELD:

For each requirement, audit:

- requirement
- how_to_verify
- if_not_met

The requirement must clearly identify the genuinely missing information.

how_to_verify must describe a safe way to resolve that information.
For a user preference, asking the user is appropriate.

if_not_met must preserve the no-plan boundary rather than silently
selecting or executing a plan without the required information.

ISSUE TYPES:

- hidden_assumption:
  ZERO assumes missing information or user intent rather than confirming
  it, or asks for information that is actually already known.

- safety_or_uncertainty:
  NEEDS_CONFIRMATION is the wrong boundary because the uncertainty only
  gates execution of an already-selected plan, or because the requested
  confirmation would not actually determine plan selection.

- unsupported_physical_claim:
  explanation/requirement states a physical fact not grounded by the
  evidence.

- unsupported_capability:
  explanation/requirement misstates what an object can or cannot do.

- constraint_violation:
  reasoning conflicts with a user constraint.

- unlisted_resource:
  confirmation depends on a resource that is not available.

SEVERITY:

Use MEDIUM or HIGH when the issue can change whether
NEEDS_CONFIRMATION is a valid terminal outcome.

LOW findings do not block the outcome.

COVERAGE CONTRACT:

You MUST audit every field listed in SEMANTIC FIELD CHECKLIST.

Return a "coverage" object with EXACTLY the same field IDs.

Each coverage value is a list of 1-based finding numbers.

[] means the field was explicitly audited and no finding applies.

Every finding must be referenced by at least one field.

There is no PhysicalPlan, so every finding MUST use:

"step_order": null

Do not return your own passed/failed boolean.
ZERO derives pass/fail deterministically from validated finding severity.

RETURN ONLY JSON:

{{
  "findings": [
    {{
      "step_order": null,
      "claim": "short problematic confirmation claim",
      "issue_type": "unlisted_resource | unsupported_physical_claim | unsupported_capability | hidden_assumption | safety_or_uncertainty | constraint_violation",
      "severity": "low | medium | high",
      "explanation": "brief grounding explanation",
      "recommended_fix": "brief specific correction"
    }}
  ],
  "coverage": {{
    "exact-field-id": []
  }}
}}

Maximum 8 findings.

======================================================================
USER GOAL
======================================================================

{goal}

======================================================================
ACTIVE INVENTORY
======================================================================

{json.dumps(
    inventory_payload,
    indent=2,
    ensure_ascii=False,
)}

======================================================================
VALIDATED OBJECT DNA
======================================================================

{json.dumps(
    compact_dna,
    indent=2,
    ensure_ascii=False,
)}

======================================================================
EXTERNAL RESOURCES
======================================================================

{json.dumps(
    external_resources,
    indent=2,
    ensure_ascii=False,
)}

======================================================================
NEEDS_CONFIRMATION OUTCOME
======================================================================

{outcome.model_dump_json(indent=2)}

======================================================================
SEMANTIC FIELD CHECKLIST
======================================================================

{json.dumps(
    field_map,
    indent=2,
    ensure_ascii=False,
)}
""".strip()


def _parse_confirmation_critic_output(
    *,
    raw_output: str,
    required_field_ids: list[str],
) -> PlanCriticResult:
    """
    Parse exactly one confirmation-grounding response.

    No model-based JSON repair is permitted, so one audit
    can never silently turn into two paid calls.
    """

    payload = load_model_json(
        raw_output
    )

    payload = (
        semantic_critic
        ._normalize_critic_payload(
            payload
        )
    )

    envelope = (
        semantic_critic
        .SemanticAuditEnvelope
        .model_validate(
            payload
        )
    )

    semantic_critic._validate_semantic_coverage(
        envelope=envelope,
        required_field_ids=(
            required_field_ids
        ),
    )

    for finding in envelope.findings:
        if finding.step_order is not None:
            raise (
                semantic_critic
                .IncompleteSemanticCoverageError(
                    "NEEDS_CONFIRMATION findings "
                    "must use null step_order."
                )
            )

    has_blocking_findings = any(
        finding.severity
        in {
            CriticSeverity.MEDIUM,
            CriticSeverity.HIGH,
        }
        for finding
        in envelope.findings
    )

    return PlanCriticResult(
        passed=(
            not has_blocking_findings
        ),
        findings=list(
            envelope.findings
        ),
    )


def audit_needs_confirmation_semantics(
    *,
    outcome: PlanOutcome,
    goal: str,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
    external_resources: list[str] | None = None,
) -> PlanCriticResult:
    """
    Perform exactly one semantic grounding call for a
    NEEDS_CONFIRMATION outcome.
    """

    if (
        outcome.status
        != PlanOutcomeStatus.NEEDS_CONFIRMATION
    ):
        raise ValueError(
            "Confirmation semantic audit requires "
            "NEEDS_CONFIRMATION."
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
        for item
        in inventory
    ]

    compact_dna = (
        semantic_critic
        ._build_compact_dna(
            object_dna
        )
    )

    field_map = (
        _build_confirmation_field_map(
            outcome
        )
    )

    required_field_ids = list(
        field_map.keys()
    )

    prompt = (
        _build_confirmation_critic_prompt(
            outcome=outcome,
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
            field_map=field_map,
        )
    )

    response = (
        semantic_critic
        .client
        .chat
        .completions
        .create(
            model=(
                semantic_critic.MODEL
            ),

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

            max_tokens=(
                semantic_critic
                .SEMANTIC_CRITIC_MAX_TOKENS
            ),
        )
    )

    choice = response.choices[0]

    if (
        choice.finish_reason
        == "length"
    ):
        raise RuntimeError(
            "NEEDS_CONFIRMATION critic output "
            "was truncated."
        )

    refusal = getattr(
        choice.message,
        "refusal",
        None,
    )

    if refusal:
        raise RuntimeError(
            "NEEDS_CONFIRMATION critic refused "
            f"request: {refusal}"
        )

    raw_output = (
        choice.message.content
    )

    if not raw_output:
        raise RuntimeError(
            "NEEDS_CONFIRMATION critic returned "
            "no final content."
        )

    return (
        _parse_confirmation_critic_output(
            raw_output=raw_output,
            required_field_ids=(
                required_field_ids
            ),
        )
    )