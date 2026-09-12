from human_confirmation_state import (
    HumanItemCorrection,
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
    name: str,
    status: VerificationStatus,
) -> InventoryItem:
    return InventoryItem(
        id=item_id,
        name=name,
        description=(
            f"original description for {name}"
        ),
        location_hint="original location",
        source_confidence=0.7,
        verification_status=status,
        uncertainty_reason=(
            "model identity uncertain"
            if (
                status
                == VerificationStatus
                .NEEDS_CONFIRMATION
            )
            else None
        ),
    )


def make_inventory() -> CanonicalInventory:
    return CanonicalInventory(
        items=[
            make_item(
                "bag",
                name="red reusable shopping bag",
                status=(
                    VerificationStatus
                    .NEEDS_CONFIRMATION
                ),
            ),
            make_item(
                "fabric",
                name="folded fabric",
                status=(
                    VerificationStatus
                    .NEEDS_CONFIRMATION
                ),
            ),
            make_item(
                "rack",
                name="coat rack",
                status=(
                    VerificationStatus
                    .NEEDS_CONFIRMATION
                ),
            ),
            make_item(
                "desk",
                name="desk",
                status=(
                    VerificationStatus
                    .AUTO_ACCEPTED
                ),
            ),
        ]
    )


def test_legacy_state_remains_valid():
    inventory = make_inventory()

    state = (
        PersistedHumanConfirmationState(
            inventory_sha256=(
                FINGERPRINT
            ),
            confirmed_item_ids=[
                "bag"
            ],
        )
    )

    validate_confirmation_state(
        inventory=inventory,
        inventory_sha256=(
            FINGERPRINT
        ),
        state=state,
    )

    session = (
        apply_confirmation_state(
            inventory=inventory,
            inventory_sha256=(
                FINGERPRINT
            ),
            state=state,
        )
    )

    by_id = {
        item.id: item
        for item
        in session.items
    }

    assert (
        by_id["bag"]
        .verification_status
        ==
        VerificationStatus
        .USER_CONFIRMED
    )

    assert (
        by_id["bag"].name
        ==
        "red reusable shopping bag"
    )


def test_confirmed_blanket_uses_corrected_identity():
    inventory = make_inventory()

    state = (
        merge_confirmation_state(
            inventory=inventory,
            inventory_sha256=(
                FINGERPRINT
            ),
            existing_state=None,
            newly_confirmed_item_ids=[
                "fabric"
            ],
            new_item_corrections=[
                HumanItemCorrection(
                    item_id="fabric",
                    corrected_name=(
                        "blanket"
                    ),
                    corrected_description=(
                        "folded blanket on the couch"
                    ),
                    corrected_location_hint=(
                        "on the couch, partially "
                        "visible near the bottom-left "
                        "of the frame"
                    ),
                    user_note=(
                        "User identified the partially "
                        "visible folded textile as a "
                        "blanket on the couch."
                    ),
                )
            ],
        )
    )

    session = (
        apply_confirmation_state(
            inventory=inventory,
            inventory_sha256=(
                FINGERPRINT
            ),
            state=state,
        )
    )

    by_id = {
        item.id: item
        for item
        in session.items
    }

    blanket = by_id[
        "fabric"
    ]

    assert (
        blanket.name
        == "blanket"
    )

    assert (
        blanket.description
        ==
        "folded blanket on the couch"
    )

    assert (
        blanket.verification_status
        ==
        VerificationStatus
        .USER_CONFIRMED
    )

    assert (
        blanket.uncertainty_reason
        is None
    )


def test_unconfirmed_vacuum_rack_stays_blocked():
    inventory = make_inventory()

    state = (
        merge_confirmation_state(
            inventory=inventory,
            inventory_sha256=(
                FINGERPRINT
            ),
            existing_state=None,
            newly_confirmed_item_ids=[],
            new_item_corrections=[
                HumanItemCorrection(
                    item_id="rack",
                    corrected_name=(
                        "vacuum rack/stand"
                    ),
                    corrected_description=(
                        "rack or stand associated "
                        "with a vacuum"
                    ),
                    user_note=(
                        "User believes the object "
                        "was misidentified as a "
                        "coat rack."
                    ),
                )
            ],
        )
    )

    session = (
        apply_confirmation_state(
            inventory=inventory,
            inventory_sha256=(
                FINGERPRINT
            ),
            state=state,
        )
    )

    by_id = {
        item.id: item
        for item
        in session.items
    }

    rack = by_id[
        "rack"
    ]

    assert (
        rack.name
        == "vacuum rack/stand"
    )

    assert (
        rack.verification_status
        ==
        VerificationStatus
        .NEEDS_CONFIRMATION
    )

    assert (
        rack.uncertainty_reason
        ==
        "model identity uncertain"
    )


def test_unknown_correction_id_is_rejected():
    inventory = make_inventory()

    try:
        merge_confirmation_state(
            inventory=inventory,
            inventory_sha256=(
                FINGERPRINT
            ),
            existing_state=None,
            newly_confirmed_item_ids=[],
            new_item_corrections=[
                HumanItemCorrection(
                    item_id="missing",
                    corrected_name="blanket",
                )
            ],
        )

    except ValueError:
        return

    raise AssertionError(
        "Unknown correction ID was accepted."
    )


def test_new_correction_replaces_older_correction():
    inventory = make_inventory()

    first = (
        merge_confirmation_state(
            inventory=inventory,
            inventory_sha256=(
                FINGERPRINT
            ),
            existing_state=None,
            newly_confirmed_item_ids=[],
            new_item_corrections=[
                HumanItemCorrection(
                    item_id="fabric",
                    corrected_name="cloth",
                )
            ],
        )
    )

    second = (
        merge_confirmation_state(
            inventory=inventory,
            inventory_sha256=(
                FINGERPRINT
            ),
            existing_state=first,
            newly_confirmed_item_ids=[],
            new_item_corrections=[
                HumanItemCorrection(
                    item_id="fabric",
                    corrected_name="blanket",
                )
            ],
        )
    )

    assert (
        len(
            second.item_corrections
        )
        == 1
    )

    assert (
        second.item_corrections[
            0
        ].corrected_name
        == "blanket"
    )


def main():
    tests = [
        test_legacy_state_remains_valid,
        test_confirmed_blanket_uses_corrected_identity,
        test_unconfirmed_vacuum_rack_stays_blocked,
        test_unknown_correction_id_is_rejected,
        test_new_correction_replaces_older_correction,
    ]

    for test in tests:
        test()

        print(
            f"PASS: {test.__name__}"
        )

    print()
    print(
        f"{len(tests)}/{len(tests)} "
        "human correction tests passed"
    )

    print(
        "Model calls: 0"
    )


if __name__ == "__main__":
    main()