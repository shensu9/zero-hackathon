from critic_schemas import (
    PlanCriticResult,
)
from object_dna_fixture import (
    OBJECT_DNA_FIXTURE,
)
from plan_outcome_pipeline import (
    SafePlanOutcomeResult,
)
from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
)
from schemas import (
    CanonicalInventory,
    EvidenceBasis,
    ObjectAffordance,
    ObjectDNA,
    ObjectDNAResponse,
    VerificationStatus,
    CertaintyLevel,
    CapabilityType,
)
from verification_gate_schemas import (
    VerificationGateAudit,
)
from zero_orchestrator import (
    ZeroGoalRequest,
    run_zero_goal,
)


books = (
    OBJECT_DNA_FIXTURE
    .items[2]
    .model_copy(
        update={
            "verification_status":
                VerificationStatus.USER_CONFIRMED,
        }
    )
)

blanket = (
    OBJECT_DNA_FIXTURE
    .items[1]
    .model_copy(
        update={
            "verification_status":
                VerificationStatus.NEEDS_CONFIRMATION,
        }
    )
)


inventory = CanonicalInventory(
    items=[
        books,
        blanket,
    ]
)


object_dna = ObjectDNAResponse(
    objects=[
        ObjectDNA(
            item_id=books.id,

            physical_traits=[],

            affordances=[
                ObjectAffordance(
                    capability=(
                        CapabilityType.SUPPORT
                    ),

                    description=(
                        "Books can support an "
                        "appropriate lightweight object."
                    ),

                    evidence_basis=(
                        EvidenceBasis.COMMON_PROPERTY
                    ),

                    certainty=(
                        CertaintyLevel.HIGH
                    ),
                )
            ],

            unknown_properties=[],
            caution_notes=[],
        )
    ]
)


captured = {}


def fake_outcome_runner(
    *,
    goal,
    inventory,
    object_dna,
    external_resources,
):
    captured[
        "goal"
    ] = goal

    captured[
        "inventory_ids"
    ] = [
        item.id
        for item in inventory
    ]

    captured[
        "dna_ids"
    ] = [
        dna.item_id
        for dna in object_dna.objects
    ]

    captured[
        "external_resources"
    ] = list(
        external_resources
    )

    return SafePlanOutcomeResult(
        outcome=PlanOutcome(
            status=(
                PlanOutcomeStatus
                .CANNOT_SAFELY_SOLVE
            ),

            explanation=(
                "Stub planning result."
            ),

            blocking_reasons=[
                "Stub reason.",
            ],
        ),

        semantic_critic=(
            PlanCriticResult(
                passed=True,
                findings=[],
            )
        ),

        plan_repair_attempts=0,

        plan_repair_validation_failures=0,

        verification_gate_audit=(
            VerificationGateAudit(
                passed=True,
                findings=[],
            )
        ),

        gate_repair_attempts=0,
    )


request = ZeroGoalRequest(
    goal=(
        "Create a simple physical setup."
    ),

    inventory=inventory,

    external_resources=[
        "small object",
    ],
)


result = run_zero_goal(
    request,
    object_dna=object_dna,
    outcome_runner=(
        fake_outcome_runner
    ),
)


assert (
    result.pending_confirmation_item_ids
    == [
        blanket.id
    ]
)


assert (
    [
        item.id
        for item
        in result.active_inventory.items
    ]
    == [
        books.id
    ]
)


assert (
    captured[
        "inventory_ids"
    ]
    == [
        books.id
    ]
)


assert (
    captured[
        "dna_ids"
    ]
    == [
        books.id
    ]
)


assert (
    captured[
        "external_resources"
    ]
    == [
        "small object"
    ]
)


assert (
    result.planning.outcome.status
    == (
        PlanOutcomeStatus
        .CANNOT_SAFELY_SOLVE
    )
)


# ---------------------------------------------------------------------------
# STALE / MISMATCHED DNA MUST FAIL
# ---------------------------------------------------------------------------


try:
    run_zero_goal(
        request,

        object_dna=(
            ObjectDNAResponse(
                objects=[]
            )
        ),

        outcome_runner=(
            fake_outcome_runner
        ),
    )

except ValueError as exc:
    assert (
        "missing active inventory"
        in str(exc)
    )

else:
    raise AssertionError(
        "Missing Object DNA coverage "
        "should fail."
    )


print(
    "ZERO ORCHESTRATOR TEST: passed"
)

print(
    "Active inventory:",
    captured["inventory_ids"],
)

print(
    "Pending confirmation:",
    result.pending_confirmation_item_ids,
)