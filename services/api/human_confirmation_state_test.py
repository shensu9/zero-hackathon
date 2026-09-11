from human_confirmation_state import (
    PersistedHumanConfirmationState,
    apply_confirmation_state,
    merge_confirmation_state,
    validate_confirmation_state,
)
from schemas import (
    CanonicalInventory,
    InventoryItem,
    VerificationStatus,
)


FINGERPRINT = "a" * 64


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


def test_valid_state_is_accepted() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "box_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
        ]
    )

    state = PersistedHumanConfirmationState(
        inventory_sha256=FINGERPRINT,
        confirmed_item_ids=[
            "box_01",
        ],
    )

    result = validate_confirmation_state(
        inventory=inventory,
        inventory_sha256=FINGERPRINT,
        state=state,
    )

    assert result == state

    print(
        "VALID CONFIRMATION STATE TEST: passed"
    )


def test_rejects_wrong_inventory_fingerprint() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "box_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
        ]
    )

    state = PersistedHumanConfirmationState(
        inventory_sha256=("b" * 64),
        confirmed_item_ids=[
            "box_01",
        ],
    )

    try:
        validate_confirmation_state(
            inventory=inventory,
            inventory_sha256=FINGERPRINT,
            state=state,
        )

    except ValueError as exc:
        assert (
            "does not match the current canonical inventory fingerprint"
            in str(exc)
        )

        print(
            "FINGERPRINT MISMATCH TEST: passed"
        )

        return

    raise AssertionError(
        "Mismatched inventory fingerprint was not rejected."
    )


def test_rejects_duplicate_state_item_id() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "box_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
        ]
    )

    state = PersistedHumanConfirmationState(
        inventory_sha256=FINGERPRINT,
        confirmed_item_ids=[
            "box_01",
            "box_01",
        ],
    )

    try:
        validate_confirmation_state(
            inventory=inventory,
            inventory_sha256=FINGERPRINT,
            state=state,
        )

    except ValueError as exc:
        assert "duplicate item ID" in str(exc)

        print(
            "DUPLICATE STATE ID TEST: passed"
        )

        return

    raise AssertionError(
        "Duplicate persisted confirmation ID was not rejected."
    )


def test_rejects_invented_state_item_id() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "box_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
        ]
    )

    state = PersistedHumanConfirmationState(
        inventory_sha256=FINGERPRINT,
        confirmed_item_ids=[
            "invented_99",
        ],
    )

    try:
        validate_confirmation_state(
            inventory=inventory,
            inventory_sha256=FINGERPRINT,
            state=state,
        )

    except ValueError as exc:
        assert (
            "not present in canonical inventory"
            in str(exc)
        )

        print(
            "INVENTED STATE ID TEST: passed"
        )

        return

    raise AssertionError(
        "Invented persisted confirmation ID was not rejected."
    )


def test_rejects_originally_active_item_in_state() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "desk_01",
                status=VerificationStatus.AUTO_ACCEPTED,
            ),
        ]
    )

    state = PersistedHumanConfirmationState(
        inventory_sha256=FINGERPRINT,
        confirmed_item_ids=[
            "desk_01",
        ],
    )

    try:
        validate_confirmation_state(
            inventory=inventory,
            inventory_sha256=FINGERPRINT,
            state=state,
        )

    except ValueError as exc:
        assert (
            "was not NEEDS_CONFIRMATION in the source inventory"
            in str(exc)
        )

        print(
            "ACTIVE SOURCE ITEM STATE REJECTION TEST: passed"
        )

        return

    raise AssertionError(
        "Originally active item was allowed into confirmation state."
    )


def test_merge_creates_new_state_in_canonical_order() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "first_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
            make_item(
                "second_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
            make_item(
                "third_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
        ]
    )

    result = merge_confirmation_state(
        inventory=inventory,
        inventory_sha256=FINGERPRINT,
        existing_state=None,
        newly_confirmed_item_ids=[
            "third_01",
            "first_01",
        ],
    )

    assert result.confirmed_item_ids == [
        "first_01",
        "third_01",
    ]

    print(
        "CANONICAL MERGE ORDER TEST: passed"
    )


def test_merge_is_idempotent_for_existing_confirmation() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "box_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
        ]
    )

    existing = PersistedHumanConfirmationState(
        inventory_sha256=FINGERPRINT,
        confirmed_item_ids=[
            "box_01",
        ],
    )

    result = merge_confirmation_state(
        inventory=inventory,
        inventory_sha256=FINGERPRINT,
        existing_state=existing,
        newly_confirmed_item_ids=[
            "box_01",
        ],
    )

    assert result.confirmed_item_ids == [
        "box_01",
    ]

    print(
        "IDEMPOTENT MERGE TEST: passed"
    )


def test_merge_rejects_duplicate_new_confirmation() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "box_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
        ]
    )

    try:
        merge_confirmation_state(
            inventory=inventory,
            inventory_sha256=FINGERPRINT,
            existing_state=None,
            newly_confirmed_item_ids=[
                "box_01",
                "box_01",
            ],
        )

    except ValueError as exc:
        assert (
            "New human confirmations contain duplicate item ID"
            in str(exc)
        )

        print(
            "DUPLICATE NEW CONFIRMATION TEST: passed"
        )

        return

    raise AssertionError(
        "Duplicate new confirmation was not rejected."
    )


def test_apply_state_promotes_only_confirmed_items() -> None:
    pending_confirmed = make_item(
        "box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    pending_unconfirmed = make_item(
        "blanket_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    auto_accepted = make_item(
        "desk_01",
        status=VerificationStatus.AUTO_ACCEPTED,
    )

    inventory = CanonicalInventory(
        items=[
            auto_accepted,
            pending_confirmed,
            pending_unconfirmed,
        ]
    )

    state = PersistedHumanConfirmationState(
        inventory_sha256=FINGERPRINT,
        confirmed_item_ids=[
            "box_01",
        ],
    )

    result = apply_confirmation_state(
        inventory=inventory,
        inventory_sha256=FINGERPRINT,
        state=state,
    )

    by_id = {
        item.id: item
        for item in result.items
    }

    assert (
        by_id[
            "box_01"
        ].verification_status
        == VerificationStatus.USER_CONFIRMED
    )

    assert (
        by_id[
            "box_01"
        ].uncertainty_reason
        is None
    )

    assert (
        by_id[
            "blanket_01"
        ].verification_status
        == VerificationStatus.NEEDS_CONFIRMATION
    )

    assert (
        by_id[
            "desk_01"
        ].verification_status
        == VerificationStatus.AUTO_ACCEPTED
    )

    print(
        "APPLY STATE EXACT PROMOTION TEST: passed"
    )


def test_apply_state_does_not_mutate_source_inventory() -> None:
    pending = make_item(
        "box_01",
        status=VerificationStatus.NEEDS_CONFIRMATION,
    )

    inventory = CanonicalInventory(
        items=[pending]
    )

    state = PersistedHumanConfirmationState(
        inventory_sha256=FINGERPRINT,
        confirmed_item_ids=[
            "box_01",
        ],
    )

    result = apply_confirmation_state(
        inventory=inventory,
        inventory_sha256=FINGERPRINT,
        state=state,
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
        result.items[
            0
        ].verification_status
        == VerificationStatus.USER_CONFIRMED
    )

    print(
        "SOURCE INVENTORY IMMUTABILITY TEST: passed"
    )


def test_rejects_duplicate_canonical_inventory_id() -> None:
    inventory = CanonicalInventory(
        items=[
            make_item(
                "box_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
            make_item(
                "box_01",
                status=VerificationStatus.NEEDS_CONFIRMATION,
            ),
        ]
    )

    state = PersistedHumanConfirmationState(
        inventory_sha256=FINGERPRINT,
        confirmed_item_ids=[],
    )

    try:
        validate_confirmation_state(
            inventory=inventory,
            inventory_sha256=FINGERPRINT,
            state=state,
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
    test_valid_state_is_accepted()

    test_rejects_wrong_inventory_fingerprint()

    test_rejects_duplicate_state_item_id()

    test_rejects_invented_state_item_id()

    test_rejects_originally_active_item_in_state()

    test_merge_creates_new_state_in_canonical_order()

    test_merge_is_idempotent_for_existing_confirmation()

    test_merge_rejects_duplicate_new_confirmation()

    test_apply_state_promotes_only_confirmed_items()

    test_apply_state_does_not_mutate_source_inventory()

    test_rejects_duplicate_canonical_inventory_id()

    print()

    print(
        "HUMAN CONFIRMATION STATE TEST: passed"
    )


if __name__ == "__main__":
    main()