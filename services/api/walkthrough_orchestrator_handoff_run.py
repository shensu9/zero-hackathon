from critic_schemas import (
    PlanCriticResult,
)
from human_confirmation_state import (
    apply_confirmation_state,
)
from plan_outcome_pipeline import (
    SafePlanOutcomeResult,
)
from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
)
from schemas import (
    ObjectDNA,
    ObjectDNAResponse,
    VerificationStatus,
)
from verification_gate_schemas import (
    VerificationGateAudit,
)
from walkthrough_goal_relevance_run import (
    GOAL,
    inventory_fingerprint,
    load_inventory,
)
from walkthrough_human_confirmation_run import (
    load_existing_confirmation_state,
)
from zero_orchestrator import (
    ZeroGoalRequest,
    run_zero_goal,
)


CONFIRMED_BOX_ID = "cardboard_box_f08_o12"


def build_session_inventory():
    """
    Reconstruct the real walkthrough session inventory from:

        immutable CanonicalInventory
        +
        persisted explicit human confirmation state

    No AI/model call is made.
    """

    canonical_inventory = load_inventory()

    fingerprint = inventory_fingerprint(
        canonical_inventory
    )

    state = load_existing_confirmation_state(
        inventory=canonical_inventory,
        fingerprint=fingerprint,
    )

    if state is None:
        raise RuntimeError(
            "Persisted human confirmation state was not found."
        )

    session_inventory = apply_confirmation_state(
        inventory=canonical_inventory,
        inventory_sha256=fingerprint,
        state=state,
    )

    return (
        canonical_inventory,
        session_inventory,
        state,
        fingerprint,
    )


def build_synthetic_object_dna(
    session_inventory,
) -> ObjectDNAResponse:
    """
    Build zero-semantic synthetic Object DNA for every item currently
    eligible for downstream reasoning.

    This exists only to test the orchestrator handoff and coverage contract.

    It does NOT claim any physical capabilities and makes no model call.
    """

    objects = []

    for item in session_inventory.items:
        if (
            item.verification_status
            == VerificationStatus.NEEDS_CONFIRMATION
        ):
            continue

        objects.append(
            ObjectDNA(
                item_id=item.id,
                physical_traits=[],
                affordances=[],
                unknown_properties=[],
                caution_notes=[],
            )
        )

    return ObjectDNAResponse(
        objects=objects
    )


def build_stub_outcome() -> SafePlanOutcomeResult:
    """
    Produce a deterministic downstream result without invoking planning.
    """

    return SafePlanOutcomeResult(
        outcome=PlanOutcome(
            status=(
                PlanOutcomeStatus.CANNOT_SAFELY_SOLVE
            ),
            explanation=(
                "Deterministic orchestrator handoff test."
            ),
            blocking_reasons=[
                "Planning intentionally stubbed for this test.",
            ],
        ),
        semantic_critic=PlanCriticResult(
            passed=True,
            findings=[],
        ),
        plan_repair_attempts=0,
        plan_repair_validation_failures=0,
        verification_gate_audit=VerificationGateAudit(
            passed=True,
            findings=[],
        ),
        gate_repair_attempts=0,
    )


def main() -> None:
    print("=" * 72)
    print("ZERO WALKTHROUGH ORCHESTRATOR HANDOFF")
    print("=" * 72)

    (
        canonical_inventory,
        session_inventory,
        state,
        fingerprint,
    ) = build_session_inventory()

    canonical_auto = [
        item
        for item in canonical_inventory.items
        if (
            item.verification_status
            == VerificationStatus.AUTO_ACCEPTED
        )
    ]

    canonical_pending = [
        item
        for item in canonical_inventory.items
        if (
            item.verification_status
            == VerificationStatus.NEEDS_CONFIRMATION
        )
    ]

    session_confirmed = [
        item
        for item in session_inventory.items
        if (
            item.verification_status
            == VerificationStatus.USER_CONFIRMED
        )
    ]

    session_pending = [
        item
        for item in session_inventory.items
        if (
            item.verification_status
            == VerificationStatus.NEEDS_CONFIRMATION
        )
    ]

    expected_active_items = [
        item
        for item in session_inventory.items
        if (
            item.verification_status
            != VerificationStatus.NEEDS_CONFIRMATION
        )
    ]

    expected_active_ids = [
        item.id
        for item in expected_active_items
    ]

    expected_pending_ids = [
        item.id
        for item in session_pending
    ]

    if len(canonical_inventory.items) != 85:
        raise RuntimeError(
            "Unexpected canonical inventory size: "
            f"{len(canonical_inventory.items)}"
        )

    if len(canonical_auto) != 32:
        raise RuntimeError(
            "Unexpected canonical AUTO_ACCEPTED count: "
            f"{len(canonical_auto)}"
        )

    if len(canonical_pending) != 53:
        raise RuntimeError(
            "Unexpected canonical NEEDS_CONFIRMATION count: "
            f"{len(canonical_pending)}"
        )

    if state.confirmed_item_ids != [
        CONFIRMED_BOX_ID
    ]:
        raise RuntimeError(
            "Unexpected persisted human confirmations: "
            f"{state.confirmed_item_ids}"
        )

    if len(session_confirmed) != 1:
        raise RuntimeError(
            "Expected exactly one USER_CONFIRMED item, received "
            f"{len(session_confirmed)}."
        )

    if (
        session_confirmed[0].id
        != CONFIRMED_BOX_ID
    ):
        raise RuntimeError(
            "Unexpected USER_CONFIRMED item: "
            f"{session_confirmed[0].id}"
        )

    if len(expected_active_items) != 33:
        raise RuntimeError(
            "Expected 33 downstream-eligible items, received "
            f"{len(expected_active_items)}."
        )

    if len(session_pending) != 52:
        raise RuntimeError(
            "Expected 52 remaining pending items, received "
            f"{len(session_pending)}."
        )

    synthetic_object_dna = (
        build_synthetic_object_dna(
            session_inventory
        )
    )

    if (
        len(synthetic_object_dna.objects)
        != 33
    ):
        raise RuntimeError(
            "Synthetic Object DNA coverage does not match the "
            "expected active inventory."
        )

    captured = {}

    def fake_outcome_runner(
        *,
        goal,
        inventory,
        object_dna,
        external_resources,
    ):
        captured["goal"] = goal

        captured["inventory_ids"] = [
            item.id
            for item in inventory
        ]

        captured["dna_ids"] = [
            dna.item_id
            for dna in object_dna.objects
        ]

        captured["external_resources"] = list(
            external_resources
        )

        return build_stub_outcome()

    request = ZeroGoalRequest(
        goal=GOAL,
        inventory=session_inventory,
        external_resources=[],
    )

    result = run_zero_goal(
        request,
        object_dna=synthetic_object_dna,
        outcome_runner=fake_outcome_runner,
    )

    result_active_ids = [
        item.id
        for item in result.active_inventory.items
    ]

    if result_active_ids != expected_active_ids:
        raise RuntimeError(
            "zero_orchestrator active inventory does not exactly "
            "match reconstructed session eligibility."
        )

    if (
        result.pending_confirmation_item_ids
        != expected_pending_ids
    ):
        raise RuntimeError(
            "zero_orchestrator pending confirmation IDs do not "
            "exactly match the remaining session pending inventory."
        )

    if (
        captured["inventory_ids"]
        != expected_active_ids
    ):
        raise RuntimeError(
            "Planning boundary received incorrect active inventory."
        )

    if (
        captured["dna_ids"]
        != expected_active_ids
    ):
        raise RuntimeError(
            "Planning boundary received Object DNA coverage that does "
            "not exactly match active inventory."
        )

    if (
        CONFIRMED_BOX_ID
        not in captured["inventory_ids"]
    ):
        raise RuntimeError(
            "Persisted USER_CONFIRMED box did not reach the "
            "downstream planning boundary."
        )

    pending_set = set(
        expected_pending_ids
    )

    leaked_pending_ids = [
        item_id
        for item_id in captured["inventory_ids"]
        if item_id in pending_set
    ]

    if leaked_pending_ids:
        raise RuntimeError(
            "NEEDS_CONFIRMATION items leaked into downstream "
            f"reasoning: {leaked_pending_ids}"
        )

    print()
    print(
        f"Inventory SHA-256: {fingerprint}"
    )

    print()
    print("=" * 72)
    print("SESSION INPUT")
    print("=" * 72)

    print(
        f"Canonical items: "
        f"{len(canonical_inventory.items)}"
    )

    print(
        f"Persisted USER_CONFIRMED items: "
        f"{len(session_confirmed)}"
    )

    print(
        f"Expected active items: "
        f"{len(expected_active_items)}"
    )

    print(
        f"Expected pending items: "
        f"{len(expected_pending_ids)}"
    )

    print()
    print("=" * 72)
    print("ZERO ORCHESTRATOR RESULT")
    print("=" * 72)

    print(
        f"Active inventory: "
        f"{len(result.active_inventory.items)}"
    )

    print(
        f"Pending confirmation: "
        f"{len(result.pending_confirmation_item_ids)}"
    )

    print(
        f"Injected Object DNA items: "
        f"{len(synthetic_object_dna.objects)}"
    )

    print(
        "Planning/model calls: 0"
    )

    print()

    print(
        f"Confirmed box reached downstream: "
        f"{CONFIRMED_BOX_ID in captured['inventory_ids']}"
    )

    print(
        f"Pending items leaked downstream: "
        f"{len(leaked_pending_ids)}"
    )

    print()

    print(
        "ORCHESTRATOR SESSION HANDOFF TEST: passed"
    )


if __name__ == "__main__":
    main()