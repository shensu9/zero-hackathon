from pydantic import BaseModel, Field

from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
)
from plan_outcome_service import (
    generate_plan_outcome,
)
from plan_validator import (
    validate_zero_plan,
)
from schemas import (
    InventoryItem,
    ObjectDNAResponse,
)
from verification_gate_auditor import (
    audit_verification_gates,
)
from verification_gate_repair import (
    repair_verification_requirements,
)
from verification_gate_schemas import (
    VerificationGateAudit,
)


MAX_GATE_REPAIR_ATTEMPTS = 1


class UnsafeVerificationGateError(
    RuntimeError
):
    pass


class SafePlanOutcomeResult(BaseModel):
    outcome: PlanOutcome

    verification_gate_audit: (
        VerificationGateAudit
    )

    gate_repair_attempts: int = Field(
        ge=0,
        le=MAX_GATE_REPAIR_ATTEMPTS,
    )


def _valid_item_ids(
    inventory: list[InventoryItem],
) -> set[str]:
    return {
        item.id
        for item in inventory
    }


def _hard_validate_outcome_plan(
    *,
    outcome: PlanOutcome,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
) -> PlanOutcome:
    """
    Any executable plan exposed by an outcome must pass ZERO's
    existing deterministic capability validator.

    Outcome semantics never weaken PhysicalPlan grounding.
    """

    if outcome.plan is None:
        return outcome

    validated_plan = validate_zero_plan(
        outcome.plan,
        object_dna,
        _valid_item_ids(
            inventory
        ),
    )

    payload = outcome.model_dump(
        mode="json"
    )

    payload["plan"] = (
        validated_plan.model_dump(
            mode="json"
        )
    )

    return PlanOutcome.model_validate(
        payload
    )


def _replace_requirements(
    *,
    outcome: PlanOutcome,
    requirements,
) -> PlanOutcome:
    payload = outcome.model_dump(
        mode="json"
    )

    payload["requirements"] = [
        requirement.model_dump(
            mode="json"
        )
        for requirement
        in requirements
    ]

    return PlanOutcome.model_validate(
        payload
    )


def generate_safe_plan_outcome(
    *,
    goal: str,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
    external_resources=None,
) -> SafePlanOutcomeResult:
    """
    Production boundary for outcome-aware ZERO planning.

    Flow:

    model outcome
        ->
    PlanOutcome schema
        ->
    deterministic PhysicalPlan validation
        ->
    conditional verification-gate audit
        ->
    at most one requirement-only repair
        ->
    re-audit
        ->
    return only a safe outcome
    """

    external_resources = list(
        external_resources
        or []
    )

    outcome = generate_plan_outcome(
        goal=goal,
        inventory=inventory,
        object_dna=object_dna,
        external_resources=external_resources,
    )

    outcome = _hard_validate_outcome_plan(
        outcome=outcome,
        inventory=inventory,
        object_dna=object_dna,
    )

    gate_audit = (
        audit_verification_gates(
            outcome
        )
    )

    gate_repair_attempts = 0

    while (
        outcome.status
        == PlanOutcomeStatus.CONDITIONAL
        and not gate_audit.passed
        and gate_repair_attempts
        < MAX_GATE_REPAIR_ATTEMPTS
    ):
        gate_repair_attempts += 1

        print(
            "Conditional verification gate rejected; "
            "repairing requirements..."
        )

        repaired_requirements = (
            repair_verification_requirements(
                outcome=outcome,
                audit=gate_audit,
            )
        )

        outcome = _replace_requirements(
            outcome=outcome,
            requirements=(
                repaired_requirements
            ),
        )

        # The executable plan was preserved verbatim by the repair
        # layer, but validate the outcome plan again anyway so the
        # production boundary remains explicit.
        outcome = (
            _hard_validate_outcome_plan(
                outcome=outcome,
                inventory=inventory,
                object_dna=object_dna,
            )
        )

        gate_audit = (
            audit_verification_gates(
                outcome
            )
        )

    if not gate_audit.passed:
        raise UnsafeVerificationGateError(
            "ZERO could not produce a safe "
            "conditional verification gate "
            "within the bounded repair limit. "
            f"Findings: "
            f"{gate_audit.model_dump_json()}"
        )

    return SafePlanOutcomeResult(
        outcome=outcome,
        verification_gate_audit=(
            gate_audit
        ),
        gate_repair_attempts=(
            gate_repair_attempts
        ),
    )