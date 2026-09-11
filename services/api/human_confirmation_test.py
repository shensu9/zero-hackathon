from goal_scoped_confirmation import (
    GoalScopedConfirmationCandidate,
    GoalScopedConfirmationSelection,
)
from human_confirmation import (
    apply_explicit_user_confirmations,
)
from schemas import (
    CanonicalInventory,
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


def make_candidate(
    item: InventoryItem,
) -> GoalScopedConfirmationCandidate:
    return GoalScopedConfirmationCandidate(
        item=item,
        relevance=RelevanceLabel.RELEVANT,
        relevance_reason="Materially useful for the current goal.",
    )


def test_explicit_candidate_confirmation_promotes_exact_item() -> None:
    pending = make_item(
        "cardboard_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    auto_accepted = make_item(
        "desk_01",
        status=VerificationStatus.AUTO_ACCEPTED,
    )

    inventory = CanonicalInventory(
        items=[
            auto_accepted,
            pending,
        ]
    )

    selection = GoalScopedConfirmationSelection(
        candidates=[
            make_candidate(pending),
        ],
        deferred_possible_item_ids=[],
        not_relevant_pending_item_ids=[],
    )

    result = apply_explicit_user_confirmations(
        inventory=inventory,
        selection=selection,
        confirmed_item_ids=[
            "cardboard_box_01",
        ],
    )

    assert result.confirmed_item_ids == [
        "cardboard_box_01",
    ]

    assert (
        result.unconfirmed_candidate_item_ids
        == []
    )

    assert [
        item.id
        for item in result.inventory.items
    ] == [
        "desk_01",
        "cardboard_box_01",
    ]

    updated = {
        item.id: item
        for item in result.inventory.items
    }

    assert (
        updated[
            "cardboard_box_01"
        ].verification_status
        == VerificationStatus.USER_CONFIRMED
    )

    assert (
        updated[
            "cardboard_box_01"
        ].uncertainty_reason
        is None
    )

    assert (
        updated[
            "desk_01"
        ].verification_status
        == VerificationStatus.AUTO_ACCEPTED
    )

    print(
        "EXPLICIT CANDIDATE CONFIRMATION TEST: passed"
    )


def test_input_inventory_is_not_mutated() -> None:
    pending = make_item(
        "cardboard_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    inventory = CanonicalInventory(
        items=[pending]
    )

    selection = GoalScopedConfirmationSelection(
        candidates=[
            make_candidate(pending),
        ],
        deferred_possible_item_ids=[],
        not_relevant_pending_item_ids=[],
    )

    result = apply_explicit_user_confirmations(
        inventory=inventory,
        selection=selection,
        confirmed_item_ids=[
            "cardboard_box_01",
        ],
    )

    assert (
        inventory.items[
            0
        ].verification_status
        == VerificationStatus.NEEDS_CONFIRMATION
    )

    assert (
        inventory.items[
            0
        ].uncertainty_reason
        == "Test uncertainty."
    )

    assert (
        result.inventory.items[
            0
        ].verification_status
        == VerificationStatus.USER_CONFIRMED
    )

    print(
        "INPUT INVENTORY IMMUTABILITY TEST: passed"
    )


def test_unconfirmed_candidate_remains_pending() -> None:
    pending = make_item(
        "cardboard_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    inventory = CanonicalInventory(
        items=[pending]
    )

    selection = GoalScopedConfirmationSelection(
        candidates=[
            make_candidate(pending),
        ],
        deferred_possible_item_ids=[],
        not_relevant_pending_item_ids=[],
    )

    result = apply_explicit_user_confirmations(
        inventory=inventory,
        selection=selection,
        confirmed_item_ids=[],
    )

    assert result.confirmed_item_ids == []

    assert (
        result.unconfirmed_candidate_item_ids
        == ["cardboard_box_01"]
    )

    assert (
        result.inventory.items[
            0
        ].verification_status
        == VerificationStatus.NEEDS_CONFIRMATION
    )

    print(
        "UNCONFIRMED CANDIDATE REMAINS PENDING TEST: passed"
    )


def test_rejects_deferred_item_confirmation() -> None:
    candidate = make_item(
        "cardboard_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    deferred = make_item(
        "blanket_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    inventory = CanonicalInventory(
        items=[
            candidate,
            deferred,
        ]
    )

    selection = GoalScopedConfirmationSelection(
        candidates=[
            make_candidate(candidate),
        ],
        deferred_possible_item_ids=[
            "blanket_01",
        ],
        not_relevant_pending_item_ids=[],
    )

    try:
        apply_explicit_user_confirmations(
            inventory=inventory,
            selection=selection,
            confirmed_item_ids=[
                "blanket_01",
            ],
        )

    except ValueError as exc:
        assert (
            "not presented as an immediate confirmation candidate"
            in str(exc)
        )

        print(
            "DEFERRED ITEM CONFIRMATION REJECTION TEST: passed"
        )

        return

    raise AssertionError(
        "Deferred item was incorrectly allowed to become USER_CONFIRMED."
    )


def test_rejects_not_relevant_item_confirmation() -> None:
    candidate = make_item(
        "cardboard_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    irrelevant = make_item(
        "shoe_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    inventory = CanonicalInventory(
        items=[
            candidate,
            irrelevant,
        ]
    )

    selection = GoalScopedConfirmationSelection(
        candidates=[
            make_candidate(candidate),
        ],
        deferred_possible_item_ids=[],
        not_relevant_pending_item_ids=[
            "shoe_box_01",
        ],
    )

    try:
        apply_explicit_user_confirmations(
            inventory=inventory,
            selection=selection,
            confirmed_item_ids=[
                "shoe_box_01",
            ],
        )

    except ValueError as exc:
        assert (
            "not presented as an immediate confirmation candidate"
            in str(exc)
        )

        print(
            "NOT-RELEVANT ITEM CONFIRMATION REJECTION TEST: passed"
        )

        return

    raise AssertionError(
        "Not-relevant item was incorrectly allowed to become USER_CONFIRMED."
    )


def test_rejects_arbitrary_inventory_item_confirmation() -> None:
    candidate = make_item(
        "cardboard_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    hidden_pending = make_item(
        "power_strip_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    inventory = CanonicalInventory(
        items=[
            candidate,
            hidden_pending,
        ]
    )

    selection = GoalScopedConfirmationSelection(
        candidates=[
            make_candidate(candidate),
        ],
        deferred_possible_item_ids=[],
        not_relevant_pending_item_ids=[],
    )

    try:
        apply_explicit_user_confirmations(
            inventory=inventory,
            selection=selection,
            confirmed_item_ids=[
                "power_strip_01",
            ],
        )

    except ValueError as exc:
        assert (
            "not presented as an immediate confirmation candidate"
            in str(exc)
        )

        print(
            "ARBITRARY PENDING CONFIRMATION REJECTION TEST: passed"
        )

        return

    raise AssertionError(
        "Unpresented pending item was incorrectly confirmed."
    )


def test_rejects_duplicate_confirmation_id() -> None:
    pending = make_item(
        "cardboard_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    inventory = CanonicalInventory(
        items=[pending]
    )

    selection = GoalScopedConfirmationSelection(
        candidates=[
            make_candidate(pending),
        ],
        deferred_possible_item_ids=[],
        not_relevant_pending_item_ids=[],
    )

    try:
        apply_explicit_user_confirmations(
            inventory=inventory,
            selection=selection,
            confirmed_item_ids=[
                "cardboard_box_01",
                "cardboard_box_01",
            ],
        )

    except ValueError as exc:
        assert (
            "duplicate item ID"
            in str(exc)
        )

        print(
            "DUPLICATE USER CONFIRMATION ID TEST: passed"
        )

        return

    raise AssertionError(
        "Duplicate explicit confirmation ID was not rejected."
    )


def test_rejects_duplicate_selection_candidate() -> None:
    pending = make_item(
        "cardboard_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    inventory = CanonicalInventory(
        items=[pending]
    )

    selection = GoalScopedConfirmationSelection(
        candidates=[
            make_candidate(pending),
            make_candidate(pending),
        ],
        deferred_possible_item_ids=[],
        not_relevant_pending_item_ids=[],
    )

    try:
        apply_explicit_user_confirmations(
            inventory=inventory,
            selection=selection,
            confirmed_item_ids=[
                "cardboard_box_01",
            ],
        )

    except ValueError as exc:
        assert (
            "duplicate candidate ID"
            in str(exc)
        )

        print(
            "DUPLICATE SELECTION CANDIDATE TEST: passed"
        )

        return

    raise AssertionError(
        "Duplicate selection candidate was not rejected."
    )


def test_rejects_selection_candidate_missing_from_inventory() -> None:
    real_pending = make_item(
        "cardboard_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    invented_pending = make_item(
        "invented_item_99",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    inventory = CanonicalInventory(
        items=[real_pending]
    )

    selection = GoalScopedConfirmationSelection(
        candidates=[
            make_candidate(invented_pending),
        ],
        deferred_possible_item_ids=[],
        not_relevant_pending_item_ids=[],
    )

    try:
        apply_explicit_user_confirmations(
            inventory=inventory,
            selection=selection,
            confirmed_item_ids=[],
        )

    except ValueError as exc:
        assert (
            "not present in canonical inventory"
            in str(exc)
        )

        print(
            "MISSING INVENTORY CANDIDATE TEST: passed"
        )

        return

    raise AssertionError(
        "Selection candidate missing from inventory was not rejected."
    )


def test_rejects_candidate_that_is_no_longer_pending() -> None:
    stale_candidate_item = make_item(
        "cardboard_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    current_item = make_item(
        "cardboard_box_01",
        status=VerificationStatus.USER_CONFIRMED,
    )

    inventory = CanonicalInventory(
        items=[current_item]
    )

    selection = GoalScopedConfirmationSelection(
        candidates=[
            make_candidate(stale_candidate_item),
        ],
        deferred_possible_item_ids=[],
        not_relevant_pending_item_ids=[],
    )

    try:
        apply_explicit_user_confirmations(
            inventory=inventory,
            selection=selection,
            confirmed_item_ids=[
                "cardboard_box_01",
            ],
        )

    except ValueError as exc:
        assert (
            "not currently NEEDS_CONFIRMATION"
            in str(exc)
        )

        print(
            "STALE CANDIDATE STATUS TEST: passed"
        )

        return

    raise AssertionError(
        "Stale confirmation candidate was not rejected."
    )


def test_rejects_duplicate_canonical_inventory_id() -> None:
    first = make_item(
        "cardboard_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    second = make_item(
        "cardboard_box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    inventory = CanonicalInventory(
        items=[
            first,
            second,
        ]
    )

    selection = GoalScopedConfirmationSelection(
        candidates=[],
        deferred_possible_item_ids=[],
        not_relevant_pending_item_ids=[],
    )

    try:
        apply_explicit_user_confirmations(
            inventory=inventory,
            selection=selection,
            confirmed_item_ids=[],
        )

    except ValueError as exc:
        assert (
            "Canonical inventory contains duplicate item ID"
            in str(exc)
        )

        print(
            "DUPLICATE CANONICAL INVENTORY ID TEST: passed"
        )

        return

    raise AssertionError(
        "Duplicate canonical inventory ID was not rejected."
    )


def main() -> None:
    test_explicit_candidate_confirmation_promotes_exact_item()

    test_input_inventory_is_not_mutated()

    test_unconfirmed_candidate_remains_pending()

    test_rejects_deferred_item_confirmation()

    test_rejects_not_relevant_item_confirmation()

    test_rejects_arbitrary_inventory_item_confirmation()

    test_rejects_duplicate_confirmation_id()

    test_rejects_duplicate_selection_candidate()

    test_rejects_selection_candidate_missing_from_inventory()

    test_rejects_candidate_that_is_no_longer_pending()

    test_rejects_duplicate_canonical_inventory_id()

    print()

    print(
        "HUMAN CONFIRMATION TEST: passed"
    )


if __name__ == "__main__":
    main()