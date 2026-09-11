from human_confirmation_state import (
    apply_confirmation_state,
)
from schemas import (
    CanonicalInventory,
    VerificationStatus,
)
from walkthrough_goal_relevance_run import (
    inventory_fingerprint,
    load_inventory,
)
from walkthrough_human_confirmation_run import (
    load_existing_confirmation_state,
)


def count_statuses(
    inventory: CanonicalInventory,
) -> dict[VerificationStatus, int]:
    counts = {
        VerificationStatus.AUTO_ACCEPTED: 0,
        VerificationStatus.NEEDS_CONFIRMATION: 0,
        VerificationStatus.USER_CONFIRMED: 0,
    }

    for item in inventory.items:
        counts[
            item.verification_status
        ] += 1

    return counts


def validate_session_projection(
    *,
    canonical_inventory: CanonicalInventory,
    session_inventory: CanonicalInventory,
    confirmed_item_ids: list[str],
) -> None:
    """
    Ensure persisted confirmation state changes only the intended fields.

    For explicitly confirmed items:
        NEEDS_CONFIRMATION -> USER_CONFIRMED
        uncertainty_reason -> None

    Every other canonical item must remain unchanged.
    Item order and IDs must remain identical.
    """

    canonical_ids = [
        item.id
        for item in canonical_inventory.items
    ]

    session_ids = [
        item.id
        for item in session_inventory.items
    ]

    if canonical_ids != session_ids:
        raise RuntimeError(
            "Session inventory changed canonical item order or IDs."
        )

    confirmed_id_set = set(
        confirmed_item_ids
    )

    canonical_by_id = {
        item.id: item
        for item in canonical_inventory.items
    }

    session_by_id = {
        item.id: item
        for item in session_inventory.items
    }

    for item_id in canonical_ids:
        canonical_item = canonical_by_id[
            item_id
        ]

        session_item = session_by_id[
            item_id
        ]

        if item_id in confirmed_id_set:
            if (
                canonical_item.verification_status
                != VerificationStatus.NEEDS_CONFIRMATION
            ):
                raise RuntimeError(
                    "Persisted confirmation refers to a canonical item "
                    "that was not NEEDS_CONFIRMATION: "
                    f"{item_id}"
                )

            if (
                session_item.verification_status
                != VerificationStatus.USER_CONFIRMED
            ):
                raise RuntimeError(
                    "Confirmed item was not promoted to "
                    f"USER_CONFIRMED: {item_id}"
                )

            if (
                session_item.uncertainty_reason
                is not None
            ):
                raise RuntimeError(
                    "Confirmed item still contains an uncertainty reason: "
                    f"{item_id}"
                )

            canonical_without_confirmation = (
                canonical_item.model_copy(
                    update={
                        "verification_status": (
                            VerificationStatus.USER_CONFIRMED
                        ),
                        "uncertainty_reason": None,
                    }
                )
            )

            if (
                canonical_without_confirmation
                != session_item
            ):
                raise RuntimeError(
                    "Human confirmation unexpectedly changed canonical "
                    f"item content beyond confirmation fields: {item_id}"
                )

            continue

        if canonical_item != session_item:
            raise RuntimeError(
                "Session inventory unexpectedly changed an unconfirmed "
                f"canonical item: {item_id}"
            )


def main() -> None:
    print("=" * 72)
    print("ZERO WALKTHROUGH SESSION INVENTORY")
    print("=" * 72)

    canonical_inventory = load_inventory()

    fingerprint = inventory_fingerprint(
        canonical_inventory
    )

    state = load_existing_confirmation_state(
        inventory=canonical_inventory,
        fingerprint=fingerprint,
    )

    if state is None:
        print()
        print(
            "No persisted human confirmation state found."
        )

        print(
            "Session inventory is identical to canonical inventory."
        )

        session_inventory = (
            canonical_inventory.model_copy(
                deep=True
            )
        )

        confirmed_item_ids = []

    else:
        confirmed_item_ids = list(
            state.confirmed_item_ids
        )

        session_inventory = (
            apply_confirmation_state(
                inventory=canonical_inventory,
                inventory_sha256=fingerprint,
                state=state,
            )
        )

    validate_session_projection(
        canonical_inventory=canonical_inventory,
        session_inventory=session_inventory,
        confirmed_item_ids=confirmed_item_ids,
    )

    canonical_counts = count_statuses(
        canonical_inventory
    )

    session_counts = count_statuses(
        session_inventory
    )

    print()
    print(
        f"Inventory SHA-256: {fingerprint}"
    )

    print()
    print("=" * 72)
    print("CANONICAL INVENTORY")
    print("=" * 72)

    print(
        f"Items: {len(canonical_inventory.items)}"
    )

    print(
        "AUTO_ACCEPTED: "
        f"{canonical_counts[VerificationStatus.AUTO_ACCEPTED]}"
    )

    print(
        "USER_CONFIRMED: "
        f"{canonical_counts[VerificationStatus.USER_CONFIRMED]}"
    )

    print(
        "NEEDS_CONFIRMATION: "
        f"{canonical_counts[VerificationStatus.NEEDS_CONFIRMATION]}"
    )

    print()
    print("=" * 72)
    print("RECONSTRUCTED SESSION INVENTORY")
    print("=" * 72)

    print(
        f"Items: {len(session_inventory.items)}"
    )

    print(
        "AUTO_ACCEPTED: "
        f"{session_counts[VerificationStatus.AUTO_ACCEPTED]}"
    )

    print(
        "USER_CONFIRMED: "
        f"{session_counts[VerificationStatus.USER_CONFIRMED]}"
    )

    print(
        "NEEDS_CONFIRMATION: "
        f"{session_counts[VerificationStatus.NEEDS_CONFIRMATION]}"
    )

    print()

    print(
        f"Persisted confirmed item count: "
        f"{len(confirmed_item_ids)}"
    )

    for item_id in confirmed_item_ids:
        item = next(
            item
            for item in session_inventory.items
            if item.id == item_id
        )

        print()

        print(
            f"- {item.id}"
        )

        print(
            f"  name: {item.name}"
        )

        print(
            "  session status: "
            f"{item.verification_status.value}"
        )

    active_count = (
        session_counts[
            VerificationStatus.AUTO_ACCEPTED
        ]
        + session_counts[
            VerificationStatus.USER_CONFIRMED
        ]
    )

    print()
    print("=" * 72)
    print("DOWNSTREAM ELIGIBILITY")
    print("=" * 72)

    print(
        f"Eligible for Object DNA/planning: "
        f"{active_count}"
    )

    print(
        "Still excluded pending confirmation: "
        f"{session_counts[VerificationStatus.NEEDS_CONFIRMATION]}"
    )

    print()

    print(
        "SESSION INVENTORY VALIDATION: passed"
    )


if __name__ == "__main__":
    main()