from goal_scoped_confirmation import (
    select_goal_scoped_confirmation_candidates,
)
from schemas import (
    CanonicalInventory,
    GoalAwareInventoryItem,
    GoalAwareInventoryResponse,
    InventoryItem,
    RelevanceLabel,
    VerificationStatus,
)


def make_item(
    item_id: str,
    *,
    status: VerificationStatus,
) -> InventoryItem:
    return InventoryItem(
        id=item_id,
        name=item_id.replace("_", " "),
        description=f"Test inventory item {item_id}.",
        location_hint="test location",
        source_confidence=0.85,
        verification_status=status,
        uncertainty_reason=(
            "Test uncertainty."
            if status == VerificationStatus.NEEDS_CONFIRMATION
            else None
        ),
    )


def make_relevance(
    item_id: str,
    label: RelevanceLabel,
) -> GoalAwareInventoryItem:
    return GoalAwareInventoryItem(
        item_id=item_id,
        relevance=label,
        reason=f"Test relevance decision for {item_id}.",
    )


def test_only_relevant_items_are_asked_now() -> None:
    relevant_pending = make_item(
        "cardboard_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    possible_pending = make_item(
        "blanket_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    irrelevant_pending = make_item(
        "shoe_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    auto_accepted = make_item(
        "desk_01",
        status=VerificationStatus.AUTO_ACCEPTED,
    )

    user_confirmed = make_item(
        "lamp_01",
        status=VerificationStatus.USER_CONFIRMED,
    )

    inventory = CanonicalInventory(
        items=[
            relevant_pending,
            possible_pending,
            irrelevant_pending,
            auto_accepted,
            user_confirmed,
        ]
    )

    relevance = GoalAwareInventoryResponse(
        items=[
            make_relevance(
                "cardboard_box_01",
                RelevanceLabel.RELEVANT,
            ),
            make_relevance(
                "blanket_01",
                RelevanceLabel.POSSIBLY_RELEVANT,
            ),
            make_relevance(
                "shoe_box_01",
                RelevanceLabel.NOT_RELEVANT,
            ),
        ]
    )

    result = select_goal_scoped_confirmation_candidates(
        inventory=inventory,
        relevance=relevance,
    )

    candidate_ids = [
        candidate.item.id
        for candidate in result.candidates
    ]

    assert candidate_ids == [
        "cardboard_box_01",
    ]

    assert result.deferred_possible_item_ids == [
        "blanket_01",
    ]

    assert (
        result.not_relevant_pending_item_ids
        == ["shoe_box_01"]
    )

    assert (
        result.candidates[0].relevance
        == RelevanceLabel.RELEVANT
    )

    print(
        "RELEVANT-ONLY IMMEDIATE CONFIRMATION TEST: passed"
    )


def test_selection_never_changes_verification_status() -> None:
    relevant_pending = make_item(
        "cardboard_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    possible_pending = make_item(
        "blanket_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    irrelevant_pending = make_item(
        "shoe_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    inventory = CanonicalInventory(
        items=[
            relevant_pending,
            possible_pending,
            irrelevant_pending,
        ]
    )

    relevance = GoalAwareInventoryResponse(
        items=[
            make_relevance(
                "cardboard_box_01",
                RelevanceLabel.RELEVANT,
            ),
            make_relevance(
                "blanket_01",
                RelevanceLabel.POSSIBLY_RELEVANT,
            ),
            make_relevance(
                "shoe_box_01",
                RelevanceLabel.NOT_RELEVANT,
            ),
        ]
    )

    result = select_goal_scoped_confirmation_candidates(
        inventory=inventory,
        relevance=relevance,
    )

    for item in inventory.items:
        assert (
            item.verification_status
            == VerificationStatus.NEEDS_CONFIRMATION
        )

    assert (
        result.candidates[
            0
        ].item.verification_status
        == VerificationStatus.NEEDS_CONFIRMATION
    )

    print(
        "NO AUTOMATIC CONFIRMATION TEST: passed"
    )


def test_rejects_unknown_relevance_item_id() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            )
        ]
    )

    relevance = GoalAwareInventoryResponse(
        items=[
            make_relevance(
                "invented_object_99",
                RelevanceLabel.RELEVANT,
            )
        ]
    )

    try:
        select_goal_scoped_confirmation_candidates(
            inventory=inventory,
            relevance=relevance,
        )

    except ValueError as exc:
        assert (
            "not present in canonical inventory"
            in str(exc)
        )

        print(
            "INVENTED ITEM ID REJECTION TEST: passed"
        )

        return

    raise AssertionError(
        "Unknown relevance item ID was not rejected."
    )


def test_rejects_active_inventory_relevance() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "desk_01",
                status=VerificationStatus.AUTO_ACCEPTED,
            ),
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
        ]
    )

    relevance = GoalAwareInventoryResponse(
        items=[
            make_relevance(
                "desk_01",
                RelevanceLabel.RELEVANT,
            ),
            make_relevance(
                "blanket_01",
                RelevanceLabel.NOT_RELEVANT,
            ),
        ]
    )

    try:
        select_goal_scoped_confirmation_candidates(
            inventory=inventory,
            relevance=relevance,
        )

    except ValueError as exc:
        assert (
            "not a NEEDS_CONFIRMATION inventory item"
            in str(exc)
        )

        print(
            "ACTIVE INVENTORY RELEVANCE REJECTION TEST: passed"
        )

        return

    raise AssertionError(
        "Active inventory relevance output was not rejected."
    )


def test_rejects_duplicate_relevance_item_id() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            )
        ]
    )

    relevance = GoalAwareInventoryResponse(
        items=[
            make_relevance(
                "blanket_01",
                RelevanceLabel.RELEVANT,
            ),
            make_relevance(
                "blanket_01",
                RelevanceLabel.POSSIBLY_RELEVANT,
            ),
        ]
    )

    try:
        select_goal_scoped_confirmation_candidates(
            inventory=inventory,
            relevance=relevance,
        )

    except ValueError as exc:
        assert (
            "duplicate item ID"
            in str(exc)
        )

        print(
            "DUPLICATE RELEVANCE ID TEST: passed"
        )

        return

    raise AssertionError(
        "Duplicate relevance item ID was not rejected."
    )


def test_rejects_missing_pending_relevance() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
            make_item(
                "power_strip_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
        ]
    )

    relevance = GoalAwareInventoryResponse(
        items=[
            make_relevance(
                "blanket_01",
                RelevanceLabel.RELEVANT,
            )
        ]
    )

    try:
        select_goal_scoped_confirmation_candidates(
            inventory=inventory,
            relevance=relevance,
        )

    except ValueError as exc:
        assert "power_strip_01" in str(exc)

        print(
            "MISSING PENDING RELEVANCE TEST: passed"
        )

        return

    raise AssertionError(
        "Missing pending relevance decision was not rejected."
    )


def test_rejects_duplicate_inventory_item_id() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
            make_item(
                "blanket_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
        ]
    )

    relevance = GoalAwareInventoryResponse(
        items=[
            make_relevance(
                "blanket_01",
                RelevanceLabel.RELEVANT,
            )
        ]
    )

    try:
        select_goal_scoped_confirmation_candidates(
            inventory=inventory,
            relevance=relevance,
        )

    except ValueError as exc:
        assert (
            "Canonical inventory contains duplicate item ID"
            in str(exc)
        )

        print(
            "DUPLICATE INVENTORY ID TEST: passed"
        )

        return

    raise AssertionError(
        "Duplicate canonical inventory ID was not rejected."
    )


def main() -> None:
    test_only_relevant_items_are_asked_now()

    test_selection_never_changes_verification_status()

    test_rejects_unknown_relevance_item_id()

    test_rejects_active_inventory_relevance()

    test_rejects_duplicate_relevance_item_id()

    test_rejects_missing_pending_relevance()

    test_rejects_duplicate_inventory_item_id()

    print()

    print(
        "GOAL-SCOPED CONFIRMATION POLICY TEST: passed"
    )


if __name__ == "__main__":
    main()