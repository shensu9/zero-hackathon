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


def _build_blocker_field_map(
    outcome: PlanOutcome,
) -> dict[str, str]:
    """
    Return the exact semantic fields that must be audited for a
    CANNOT_SAFELY_SOLVE outcome.
    """

    if (
        outcome.status
        != PlanOutcomeStatus.CANNOT_SAFELY_SOLVE
    ):
        raise ValueError(
            "Blocker semantic audit requires "
            "CANNOT_SAFELY_SOLVE."
        )

    fields = {
        "explanation":
            outcome.explanation,
    }

    for index, reason in enumerate(
        outcome.blocking_reasons,
        start=1,
    ):
        fields[
            f"blocking_reason:{index}"
        ] = reason

    return fields


def _build_blocker_critic_prompt(
    *,
    outcome: PlanOutcome,
    goal: str,
    inventory_payload: list[dict],
    compact_dna: list[dict],
    external_resources: list[str],
    field_map: dict[str, str],
) -> str:
    """
    Build a closed-world grounding audit for a negative ZERO outcome.
    """

    return f"""
You are ZERO's CANNOT_SAFELY_SOLVE grounding critic.

ZERO has produced a negative outcome rather than an executable plan.

Your job is NOT to invent a new plan.

Your job is to audit whether every explanation/blocking claim is
actually justified by the CURRENT grounded world model.

A CANNOT_SAFELY_SOLVE conclusion is trustworthy only when its blockers
are supported by the available inventory, validated Object DNA,
external resources, and user constraints.

IMPORTANT RULES:

- Treat the provided inventory/Object DNA as the current grounded world.
- Do NOT invent capabilities, hardware, dimensions, strength, fit,
  compatibility, mounting interfaces, or resources.
- Do NOT treat an unknown property as if it were known absent.
- A generic "hang" or "support" capability does NOT prove sufficient
  load-bearing capacity for a specific object when load capacity is
  unknown.
- A generic hook/support does NOT prove compatible attachment to the
  target object.
- If an existing relevant item has an UNKNOWN property, that unknown
  may challenge CANNOT_SAFELY_SOLVE only when resolving it could complete
  an otherwise fully grounded, constraint-compatible solution path.
- A PARTIAL COUNTEREXAMPLE IS NOT ENOUGH. Do not reject a negative outcome
  merely because one object has a generic related capability or one
  unresolved property.
- Before using an unknown property to challenge the negative outcome,
  verify that every OTHER required physical link in at least one candidate
  solution path is already grounded by inventory/Object DNA.
- For hanging or mounting tasks, reason through the complete chain:
    1. target-object connection or attachment interface,
    2. any intermediate connector/support relationship,
    3. support-to-destination attachment or compatibility,
    4. required load-bearing/stability,
    5. every user constraint.
- If a required link is ABSENT from grounded capabilities rather than merely
  UNKNOWN, do not treat an unrelated unknown property as evidence that the
  whole solution might work.
- A generic hang/support affordance for garments or another object does not
  automatically establish compatibility with the target object.
- An unknown attachment method on a support does not establish that the
  target object itself has a usable attachment interface.
- Conversely, do not invent a hypothetical solution merely because an
  unknown exists. Only flag the negative claim when a COMPLETE candidate
  path would exist if the specifically identified unknown were verified.
- Respect all user constraints exactly.
- Do not recommend buying, drilling, adhesives, or other unlisted
  resources when the goal forbids them.
- Audit the negative conclusion, not merely whether taking no action is
  safe.

ISSUE TYPES:

- unsupported_physical_claim:
  blocker states a physical fact the evidence does not establish.

- unsupported_capability:
  blocker misstates what capabilities are or are not grounded.

- hidden_assumption:
  blocker relies on an unstated assumption, including treating UNKNOWN
  as known absent/present.

- safety_or_uncertainty:
  unresolved uncertainty makes the negative conclusion too strong.

- constraint_violation:
  reasoning misstates or violates a user constraint.

- unlisted_resource:
  reasoning depends on an unavailable external resource.

SEVERITY:

Use MEDIUM or HIGH when the issue can change whether
CANNOT_SAFELY_SOLVE is a valid terminal outcome.

LOW findings do not block the outcome.

COVERAGE CONTRACT:

You MUST audit every field listed below.

Return a "coverage" object with EXACTLY the same field IDs.

Each coverage value is a list of 1-based finding numbers.

[] means that field was explicitly audited and no finding applies.

Every finding must be referenced by at least one field.

Use null for step_order because there is no PhysicalPlan.

The model must NOT return its own passed/failed boolean.
ZERO derives pass/fail deterministically from finding severity.

RETURN ONLY JSON:

{{
  "findings": [
    {{
      "step_order": null,
      "claim": "short problematic negative claim",
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
NEGATIVE OUTCOME
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


def _parse_blocker_critic_output(
    *,
    raw_output: str,
    required_field_ids: list[str],
) -> PlanCriticResult:
    """
    Parse one blocker-audit response.

    Deliberately NO model-based JSON-format repair is allowed here.
    One blocker audit therefore remains bounded to one model call.
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
                    "CANNOT_SAFELY_SOLVE blocker findings "
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


def audit_cannot_safely_solve_semantics(
    *,
    outcome: PlanOutcome,
    goal: str,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
    external_resources: list[str] | None = None,
) -> PlanCriticResult:
    """
    Perform exactly one semantic grounding call for a
    CANNOT_SAFELY_SOLVE outcome.
    """

    if (
        outcome.status
        != PlanOutcomeStatus.CANNOT_SAFELY_SOLVE
    ):
        raise ValueError(
            "Blocker semantic audit requires "
            "CANNOT_SAFELY_SOLVE."
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
        _build_blocker_field_map(
            outcome
        )
    )

    required_field_ids = list(
        field_map.keys()
    )

    prompt = (
        _build_blocker_critic_prompt(
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
            "CANNOT_SAFELY_SOLVE critic output "
            "was truncated."
        )

    refusal = getattr(
        choice.message,
        "refusal",
        None,
    )

    if refusal:
        raise RuntimeError(
            "CANNOT_SAFELY_SOLVE critic refused "
            f"request: {refusal}"
        )

    raw_output = (
        choice.message.content
    )

    if not raw_output:
        raise RuntimeError(
            "CANNOT_SAFELY_SOLVE critic returned "
            "no final content."
        )

    return _parse_blocker_critic_output(
        raw_output=raw_output,
        required_field_ids=(
            required_field_ids
        ),
    )
