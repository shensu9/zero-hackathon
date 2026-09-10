from pydantic import BaseModel, Field

from critic_schemas import (
    CriticIssueType,
    CriticSeverity,
    PlanCriticFinding,
    PlanCriticResult,
)
from plan_normalizer import (
    normalize_external_resource_ids,
)
from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
)
from plan_outcome_service import (
    generate_plan_outcome,
)
from plan_repair import (
    repair_plan,
)
from plan_validator import (
    PlanValidationError,
    normalize_plan_item_ids,
    validate_zero_plan,
)
from schemas import (
    InventoryItem,
    ObjectDNAResponse,
)
from semantic_critic import (
    audit_plan_semantics,
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


MAX_PLAN_REPAIR_ATTEMPTS = 2
MAX_GATE_REPAIR_ATTEMPTS = 1


class UnsafePhysicalPlanError(
    RuntimeError
):
    pass


class UnsafeVerificationGateError(
    RuntimeError
):
    pass


class SafePlanOutcomeResult(BaseModel):
    outcome: PlanOutcome

    semantic_critic: PlanCriticResult

    plan_repair_attempts: int = Field(
        ge=0,
        le=MAX_PLAN_REPAIR_ATTEMPTS,
    )

    plan_repair_validation_failures: int = Field(
        ge=0,
    )

    verification_gate_audit: (
        VerificationGateAudit
    )

    gate_repair_attempts: int = Field(
        ge=0,
        le=MAX_GATE_REPAIR_ATTEMPTS,
    )


# ---------------------------------------------------------------------------
# BASIC HELPERS
# ---------------------------------------------------------------------------


def _valid_item_ids(
    inventory: list[InventoryItem],
) -> set[str]:
    return {
        item.id
        for item in inventory
    }


def _empty_passed_critic(
) -> PlanCriticResult:
    """
    Non-executable outcomes have no PhysicalPlan to semantically audit.
    """

    return PlanCriticResult(
        passed=True,
        findings=[],
    )


def _replace_plan(
    *,
    outcome: PlanOutcome,
    plan,
) -> PlanOutcome:
    payload = outcome.model_dump(
        mode="json"
    )

    payload["plan"] = (
        plan.model_dump(
            mode="json"
        )
        if plan is not None
        else None
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


# ---------------------------------------------------------------------------
# CONDITIONAL EXECUTION CONTEXT
# ---------------------------------------------------------------------------


def _build_execution_aware_goal(
    *,
    goal: str,
    outcome: PlanOutcome,
) -> str:
    """
    Semantic auditing must understand CONDITIONAL execution correctly.

    A conditional PhysicalPlan does NOT execute while requirements are
    unresolved.

    It executes only after every requirement has been verified true.

    Therefore the semantic critic may treat those requirements as
    established preconditions at execution time.

    This does NOT weaken verification-gate auditing. The separate gate
    auditor determines whether the method used to establish each
    requirement is itself safe.
    """

    if (
        outcome.status
        != PlanOutcomeStatus.CONDITIONAL
    ):
        return goal

    if not outcome.requirements:
        return goal

    requirement_lines = []

    for index, requirement in enumerate(
        outcome.requirements,
        start=1,
    ):
        requirement_lines.append(
            (
                f"{index}. "
                f"{requirement.requirement} "
                f"This MUST be verified true before the "
                f"PhysicalPlan begins. If it is not met: "
                f"{requirement.if_not_met}"
            )
        )

    requirements_text = "\n".join(
        requirement_lines
    )

    return f"""
{goal}


======================================================================
CONDITIONAL EXECUTION CONTRACT
======================================================================

The PhysicalPlan being audited is NOT allowed to execute immediately.

It begins ONLY AFTER every requirement below has been verified true.

When evaluating the PhysicalPlan itself, treat these verified
requirements as established execution-time preconditions.

Do NOT flag the plan merely for relying on a property that one of these
requirements explicitly verifies before execution.

If a requirement is not met, the PhysicalPlan does not execute.

The safety or validity of HOW these requirements are verified is audited
separately by ZERO's verification-gate auditor.

VERIFIED PRECONDITIONS BEFORE PLAN EXECUTION:

{requirements_text}
""".strip()


# ---------------------------------------------------------------------------
# PLAN NORMALIZATION / HARD VALIDATION
# ---------------------------------------------------------------------------


def _normalize_plan(
    *,
    plan,
    external_resources,
):
    normalized = (
        normalize_external_resource_ids(
            plan,
            external_resources,
        )
    )

    normalized = normalize_plan_item_ids(
        normalized
    )

    return normalized


def _hard_validate_plan(
    *,
    plan,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
):
    return validate_zero_plan(
        plan,
        object_dna,
        _valid_item_ids(
            inventory
        ),
    )


def _validation_failure_to_critic(
    error: PlanValidationError,
) -> PlanCriticResult:
    """
    Convert deterministic validator feedback into the same repair
    feedback structure consumed by plan_repair.py.

    The deterministic validator remains authoritative.
    """

    error_text = str(
        error
    )

    return PlanCriticResult(
        passed=False,

        findings=[
            PlanCriticFinding(
                step_order=None,

                claim=(
                    "Plan failed deterministic "
                    "capability validation."
                ),

                issue_type=(
                    CriticIssueType.UNSUPPORTED_CAPABILITY
                ),

                severity=(
                    CriticSeverity.HIGH
                ),

                explanation=(
                    error_text
                ),

                recommended_fix=(
                    "Correct these exact deterministic "
                    "validator errors without inventing "
                    f"capabilities: {error_text}"
                ),
            )
        ],
    )


# ---------------------------------------------------------------------------
# SEMANTIC PLAN AUDIT
# ---------------------------------------------------------------------------


def _audit_outcome_plan(
    *,
    outcome: PlanOutcome,
    goal: str,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
    external_resources,
) -> PlanCriticResult:
    if outcome.plan is None:
        return _empty_passed_critic()

    execution_goal = (
        _build_execution_aware_goal(
            goal=goal,
            outcome=outcome,
        )
    )

    return audit_plan_semantics(
        plan=outcome.plan,
        goal=execution_goal,
        inventory=inventory,
        object_dna=object_dna,
        external_resources=list(
            external_resources
        ),
    )


# ---------------------------------------------------------------------------
# HARD + SEMANTIC PLAN SAFETY
# ---------------------------------------------------------------------------


def _make_outcome_plan_safe(
    *,
    outcome: PlanOutcome,
    goal: str,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
    external_resources,
) -> tuple[
    PlanOutcome,
    PlanCriticResult,
    int,
    int,
]:
    """
    Ensure any executable plan passes:

    1. deterministic capability validation
    2. semantic physical-plan criticism

    At most two total plan-repair attempts are allowed.

    An invalid or semantically unsafe plan is never returned simply
    because repair attempts were exhausted.
    """

    if outcome.plan is None:
        return (
            outcome,
            _empty_passed_critic(),
            0,
            0,
        )

    current_plan = outcome.plan

    repair_attempts = 0

    repair_validation_failures = 0

    last_critic = (
        _empty_passed_critic()
    )

    while True:
        current_plan = _normalize_plan(
            plan=current_plan,
            external_resources=(
                external_resources
            ),
        )

        # ---------------------------------------------------------------
        # HARD VALIDATION
        # ---------------------------------------------------------------

        try:
            validated_plan = (
                _hard_validate_plan(
                    plan=current_plan,
                    inventory=inventory,
                    object_dna=object_dna,
                )
            )

        except PlanValidationError as exc:
            repair_validation_failures += 1

            last_critic = (
                _validation_failure_to_critic(
                    exc
                )
            )

            print(
                "Outcome plan failed deterministic "
                "validation:"
            )

            print(
                str(exc)
            )

        else:
            # -----------------------------------------------------------
            # PLAN IS HARD-VALID. NOW AUDIT SEMANTICS.
            # -----------------------------------------------------------

            outcome = _replace_plan(
                outcome=outcome,
                plan=validated_plan,
            )

            current_plan = validated_plan

            last_critic = (
                _audit_outcome_plan(
                    outcome=outcome,
                    goal=goal,
                    inventory=inventory,
                    object_dna=object_dna,
                    external_resources=(
                        external_resources
                    ),
                )
            )

            if last_critic.passed:
                return (
                    outcome,
                    last_critic,
                    repair_attempts,
                    repair_validation_failures,
                )

            print(
                "Outcome plan failed semantic "
                "physical audit."
            )

        # ---------------------------------------------------------------
        # REPAIR BOUND
        # ---------------------------------------------------------------

        if (
            repair_attempts
            >= MAX_PLAN_REPAIR_ATTEMPTS
        ):
            raise UnsafePhysicalPlanError(
                "ZERO could not produce a plan that "
                "passes both deterministic and semantic "
                "physical validation within the bounded "
                "repair limit. "
                f"Findings: "
                f"{last_critic.model_dump_json()}"
            )

        repair_attempts += 1

        print(
            "Repairing outcome PhysicalPlan "
            f"({repair_attempts}/"
            f"{MAX_PLAN_REPAIR_ATTEMPTS})..."
        )

        execution_goal = (
            _build_execution_aware_goal(
                goal=goal,
                outcome=outcome,
            )
        )

        current_plan = repair_plan(
            plan=current_plan,
            critic=last_critic,
            goal=execution_goal,
            inventory=inventory,
            object_dna=object_dna,
            external_resources=list(
                external_resources
            ),
        )


# ---------------------------------------------------------------------------
# CONDITIONAL VERIFICATION GATE
# ---------------------------------------------------------------------------


def _make_verification_gate_safe(
    *,
    outcome: PlanOutcome,
) -> tuple[
    PlanOutcome,
    VerificationGateAudit,
    int,
]:
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

    return (
        outcome,
        gate_audit,
        gate_repair_attempts,
    )


# ---------------------------------------------------------------------------
# PRODUCTION OUTCOME BOUNDARY
# ---------------------------------------------------------------------------


def generate_safe_plan_outcome(
    *,
    goal: str,
    inventory: list[InventoryItem],
    object_dna: ObjectDNAResponse,
    external_resources=None,
) -> SafePlanOutcomeResult:
    """
    Production boundary for outcome-aware ZERO planning.

    Full flow:

    model outcome
        ->
    PlanOutcome schema
        ->
    deterministic capability validation
        ->
    semantic physical-plan audit
        ->
    bounded PhysicalPlan repair
        ->
    verification-gate audit
        ->
    bounded requirement-only gate repair
        ->
    final semantic recheck
        ->
    safe outcome

    No executable PhysicalPlan is returned unless it passes both hard
    capability grounding and semantic physical validation.
    """

    external_resources = list(
        external_resources
        or []
    )

    # ------------------------------------------------------------------
    # MODEL OUTCOME
    # ------------------------------------------------------------------

    outcome = generate_plan_outcome(
        goal=goal,
        inventory=inventory,
        object_dna=object_dna,
        external_resources=(
            external_resources
        ),
    )

    # ------------------------------------------------------------------
    # HARD + SEMANTIC PLAN SAFETY
    # ------------------------------------------------------------------

    (
        outcome,
        semantic_critic,
        plan_repair_attempts,
        plan_repair_validation_failures,
    ) = _make_outcome_plan_safe(
        outcome=outcome,
        goal=goal,
        inventory=inventory,
        object_dna=object_dna,
        external_resources=(
            external_resources
        ),
    )

    # ------------------------------------------------------------------
    # CONDITIONAL VERIFICATION SAFETY
    # ------------------------------------------------------------------

    (
        outcome,
        gate_audit,
        gate_repair_attempts,
    ) = _make_verification_gate_safe(
        outcome=outcome,
    )

    # ------------------------------------------------------------------
    # FINAL SEMANTIC RECHECK
    #
    # Requirement-only gate repair is instructed to preserve requirement
    # meaning. Still, fail closed if the final conditional envelope no
    # longer makes the PhysicalPlan semantically safe.
    # ------------------------------------------------------------------

    final_semantic_critic = (
        _audit_outcome_plan(
            outcome=outcome,
            goal=goal,
            inventory=inventory,
            object_dna=object_dna,
            external_resources=(
                external_resources
            ),
        )
    )

    if not final_semantic_critic.passed:
        raise UnsafePhysicalPlanError(
            "Final outcome failed semantic physical "
            "validation after verification-gate processing. "
            f"Findings: "
            f"{final_semantic_critic.model_dump_json()}"
        )

    return SafePlanOutcomeResult(
        outcome=outcome,

        semantic_critic=(
            final_semantic_critic
        ),

        plan_repair_attempts=(
            plan_repair_attempts
        ),

        plan_repair_validation_failures=(
            plan_repair_validation_failures
        ),

        verification_gate_audit=(
            gate_audit
        ),

        gate_repair_attempts=(
            gate_repair_attempts
        ),
    )