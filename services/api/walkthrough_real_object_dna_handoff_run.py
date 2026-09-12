import json

from critic_schemas import (
    PlanCriticResult,
)
from plan_outcome_pipeline import (
    SafePlanOutcomeResult,
)
from plan_outcome_schemas import (
    PlanOutcome,
    PlanOutcomeStatus,
)
from schemas import (
    VerificationStatus,
)
from verification_gate_schemas import (
    VerificationGateAudit,
)
from walkthrough_goal_relevance_run import (
    GOAL,
    inventory_fingerprint,
)
from walkthrough_object_dna_run import (
    AGGREGATE_PATH,
    ObjectDNAAggregateSnapshot,
    get_eligible_items,
    load_session_inventory,
    object_dna_pipeline_fingerprint,
)
from zero_orchestrator import (
    ZeroGoalRequest,
    run_zero_goal,
)


CONFIRMED_BOX_ID = "cardboard_box_f08_o12"


def load_validated_real_object_dna(
    *,
    session_inventory,
    eligible_items,
):
    """
    Load and validate the complete real cached Object DNA snapshot.

    This function makes no model calls.

    Validation guarantees:
    - aggregate file exists
    - aggregate schema is valid
    - session inventory fingerprint matches
    - Object DNA pipeline fingerprint matches
    - eligible item IDs match exactly and in canonical order
    - Object DNA coverage matches exactly
    """

    if not AGGREGATE_PATH.exists():
        raise RuntimeError(
            "Complete Object DNA aggregate snapshot was not found: "
            f"{AGGREGATE_PATH}"
        )

    try:
        payload = json.loads(
            AGGREGATE_PATH.read_text(
                encoding="utf-8"
            )
        )

        snapshot = (
            ObjectDNAAggregateSnapshot.model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Object DNA aggregate snapshot is invalid."
        ) from exc

    expected_session_sha256 = (
        inventory_fingerprint(
            session_inventory
        )
    )

    if (
        snapshot.session_inventory_sha256
        != expected_session_sha256
    ):
        raise RuntimeError(
            "Object DNA aggregate snapshot belongs to a different "
            "session inventory."
        )

    expected_pipeline_sha256 = (
        object_dna_pipeline_fingerprint()
    )

    if (
        snapshot.pipeline_sha256
        != expected_pipeline_sha256
    ):
        raise RuntimeError(
            "Object DNA aggregate snapshot was generated under a "
            "different Object DNA pipeline."
        )

    expected_ids = [
        item.id
        for item in eligible_items
    ]

    if (
        snapshot.eligible_item_ids
        != expected_ids
    ):
        raise RuntimeError(
            "Object DNA aggregate eligible-item IDs do not exactly "
            "match the current session inventory."
        )

    dna_ids = [
        dna.item_id
        for dna in snapshot.object_dna.objects
    ]

    if dna_ids != expected_ids:
        raise RuntimeError(
            "Object DNA aggregate coverage/order does not exactly "
            "match current eligible session inventory."
        )

    if (
        len(set(dna_ids))
        != len(dna_ids)
    ):
        raise RuntimeError(
            "Object DNA aggregate contains duplicate item IDs."
        )

    return snapshot


def build_stub_outcome() -> SafePlanOutcomeResult:
    """
    Deterministic downstream result.

    Real planning is intentionally disabled for this handoff test.
    """

    return SafePlanOutcomeResult(
        outcome=PlanOutcome(
            status=(
                PlanOutcomeStatus.CANNOT_SAFELY_SOLVE
            ),
            explanation=(
                "Real Object DNA handoff validated. "
                "Planning intentionally stubbed."
            ),
            blocking_reasons=[
                "Real planner was not invoked in this test.",
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
    print("ZERO REAL OBJECT DNA -> ORCHESTRATOR HANDOFF")
    print("=" * 72)

    (
        canonical_inventory,
        session_inventory,
        canonical_sha256,
    ) = load_session_inventory()

    eligible_items = get_eligible_items(
        session_inventory
    )

    pending_items = [
        item
        for item in session_inventory.items
        if (
            item.verification_status
            == VerificationStatus.NEEDS_CONFIRMATION
        )
    ]

    snapshot = load_validated_real_object_dna(
        session_inventory=session_inventory,
        eligible_items=eligible_items,
    )

    expected_active_ids = [
        item.id
        for item in eligible_items
    ]

    expected_pending_ids = [
        item.id
        for item in pending_items
    ]

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
        object_dna=snapshot.object_dna,
        outcome_runner=fake_outcome_runner,
    )

    result_active_ids = [
        item.id
        for item in result.active_inventory.items
    ]

    if (
        result_active_ids
        != expected_active_ids
    ):
        raise RuntimeError(
            "zero_orchestrator active inventory does not match "
            "the reconstructed session inventory."
        )

    if (
        result.pending_confirmation_item_ids
        != expected_pending_ids
    ):
        raise RuntimeError(
            "zero_orchestrator pending IDs do not exactly match "
            "the remaining session NEEDS_CONFIRMATION items."
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
            "Planning boundary received incorrect real Object DNA "
            "coverage or ordering."
        )

    if (
        CONFIRMED_BOX_ID
        not in captured["inventory_ids"]
    ):
        raise RuntimeError(
            "Persisted USER_CONFIRMED cardboard box did not reach "
            "the downstream boundary."
        )

    pending_set = set(
        expected_pending_ids
    )

    leaked_pending_ids = [
        item_id
        for item_id in captured["dna_ids"]
        if item_id in pending_set
    ]

    if leaked_pending_ids:
        raise RuntimeError(
            "NEEDS_CONFIRMATION items leaked into real Object DNA "
            f"handoff: {leaked_pending_ids}"
        )

    print()
    print(
        f"Canonical inventory SHA-256: "
        f"{canonical_sha256}"
    )

    print(
        "Session inventory SHA-256: "
        f"{snapshot.session_inventory_sha256}"
    )

    print(
        "Object DNA pipeline SHA-256: "
        f"{snapshot.pipeline_sha256}"
    )

    print()
    print("=" * 72)
    print("REAL WORLD MODEL")
    print("=" * 72)

    print(
        f"Session inventory items: "
        f"{len(session_inventory.items)}"
    )

    print(
        f"Active eligible items: "
        f"{len(eligible_items)}"
    )

    print(
        f"Real Object DNA items: "
        f"{len(snapshot.object_dna.objects)}"
    )

    print(
        f"Pending confirmation items: "
        f"{len(pending_items)}"
    )

    print()
    print("=" * 72)
    print("ORCHESTRATOR HANDOFF")
    print("=" * 72)

    print(
        f"Orchestrator active inventory: "
        f"{len(result.active_inventory.items)}"
    )

    print(
        f"Orchestrator pending confirmation: "
        f"{len(result.pending_confirmation_item_ids)}"
    )

    print(
        f"Planning received inventory items: "
        f"{len(captured['inventory_ids'])}"
    )

    print(
        f"Planning received Object DNA items: "
        f"{len(captured['dna_ids'])}"
    )

    print(
        "Planner/model calls: 0"
    )

    print()

    print(
        "Confirmed cardboard box reached downstream: "
        f"{CONFIRMED_BOX_ID in captured['inventory_ids']}"
    )

    print(
        "Pending Object DNA leaked downstream: "
        f"{len(leaked_pending_ids)}"
    )

    print()

    print(
        "REAL OBJECT DNA ORCHESTRATOR HANDOFF: passed"
    )


if __name__ == "__main__":
    main()