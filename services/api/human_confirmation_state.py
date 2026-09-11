from pydantic import BaseModel, Field

from schemas import (
    CanonicalInventory,
    InventoryItem,
    VerificationStatus,
)


class PersistedHumanConfirmationState(BaseModel):
    """
    Persistent human-confirmation delta for one exact canonical inventory.

    This does NOT duplicate CanonicalInventory.

    Instead, it records which original NEEDS_CONFIRMATION items the user
    explicitly confirmed as physically present.

    inventory_sha256 binds the state to the exact source inventory.
    """

    inventory_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    confirmed_item_ids: list[str] = Field(
        default_factory=list,
    )


def _validate_canonical_inventory(
    inventory: CanonicalInventory,
) -> dict[str, InventoryItem]:
    """
    Validate unique canonical IDs and return an ID lookup.
    """

    inventory_by_id: dict[
        str,
        InventoryItem,
    ] = {}

    for item in inventory.items:
        if item.id in inventory_by_id:
            raise ValueError(
                "Canonical inventory contains duplicate item ID: "
                f"{item.id}"
            )

        inventory_by_id[item.id] = item

    return inventory_by_id


def validate_confirmation_state(
    *,
    inventory: CanonicalInventory,
    inventory_sha256: str,
    state: PersistedHumanConfirmationState,
) -> PersistedHumanConfirmationState:
    """
    Validate persisted confirmations against the exact source inventory.

    Safety invariants:

    - state must belong to this exact inventory fingerprint
    - confirmed IDs must be unique
    - every confirmed ID must exist in canonical inventory
    - every persisted confirmation must originate from an item that was
      NEEDS_CONFIRMATION in the source canonical inventory
    """

    inventory_by_id = (
        _validate_canonical_inventory(
            inventory
        )
    )

    if (
        state.inventory_sha256
        != inventory_sha256
    ):
        raise ValueError(
            "Human confirmation state does not match the current "
            "canonical inventory fingerprint."
        )

    seen_ids: set[str] = set()

    for item_id in state.confirmed_item_ids:
        if item_id in seen_ids:
            raise ValueError(
                "Human confirmation state contains duplicate item ID: "
                f"{item_id}"
            )

        seen_ids.add(
            item_id
        )

        if item_id not in inventory_by_id:
            raise ValueError(
                "Human confirmation state contains an item ID that is "
                "not present in canonical inventory: "
                f"{item_id}"
            )

        item = inventory_by_id[
            item_id
        ]

        if (
            item.verification_status
            != VerificationStatus.NEEDS_CONFIRMATION
        ):
            raise ValueError(
                "Persisted human confirmation refers to an item that "
                "was not NEEDS_CONFIRMATION in the source inventory: "
                f"{item_id}"
            )

    return state


def merge_confirmation_state(
    *,
    inventory: CanonicalInventory,
    inventory_sha256: str,
    existing_state: (
        PersistedHumanConfirmationState
        | None
    ),
    newly_confirmed_item_ids: list[str],
) -> PersistedHumanConfirmationState:
    """
    Add newly explicit user confirmations to persisted state.

    The resulting ID order follows canonical inventory order rather than
    command/input order.

    Re-confirming an already persisted item is idempotent.

    Duplicate IDs inside newly_confirmed_item_ids are rejected.
    """

    inventory_by_id = (
        _validate_canonical_inventory(
            inventory
        )
    )

    if existing_state is None:
        existing_ids: set[str] = set()

    else:
        validated_existing = (
            validate_confirmation_state(
                inventory=inventory,
                inventory_sha256=inventory_sha256,
                state=existing_state,
            )
        )

        existing_ids = set(
            validated_existing.confirmed_item_ids
        )

    seen_new_ids: set[str] = set()

    for item_id in newly_confirmed_item_ids:
        if item_id in seen_new_ids:
            raise ValueError(
                "New human confirmations contain duplicate item ID: "
                f"{item_id}"
            )

        seen_new_ids.add(
            item_id
        )

        if item_id not in inventory_by_id:
            raise ValueError(
                "New human confirmation contains an item ID that is "
                "not present in canonical inventory: "
                f"{item_id}"
            )

        item = inventory_by_id[
            item_id
        ]

        if (
            item.verification_status
            != VerificationStatus.NEEDS_CONFIRMATION
        ):
            raise ValueError(
                "New human confirmation refers to an item that is not "
                "NEEDS_CONFIRMATION in the source inventory: "
                f"{item_id}"
            )

    combined_ids = (
        existing_ids
        | seen_new_ids
    )

    ordered_ids = [
        item.id
        for item in inventory.items
        if item.id in combined_ids
    ]

    return PersistedHumanConfirmationState(
        inventory_sha256=inventory_sha256,
        confirmed_item_ids=ordered_ids,
    )


def apply_confirmation_state(
    *,
    inventory: CanonicalInventory,
    inventory_sha256: str,
    state: PersistedHumanConfirmationState,
) -> CanonicalInventory:
    """
    Reconstruct a session inventory from immutable canonical inventory plus
    persisted explicit human confirmations.

    The source CanonicalInventory is never mutated.

    Only persisted confirmed IDs are promoted:
        NEEDS_CONFIRMATION -> USER_CONFIRMED
    """

    validated_state = (
        validate_confirmation_state(
            inventory=inventory,
            inventory_sha256=inventory_sha256,
            state=state,
        )
    )

    confirmed_ids = set(
        validated_state.confirmed_item_ids
    )

    updated_items: list[
        InventoryItem
    ] = []

    for item in inventory.items:
        if item.id not in confirmed_ids:
            updated_items.append(
                item.model_copy(
                    deep=True
                )
            )

            continue

        updated_items.append(
            item.model_copy(
                update={
                    "verification_status": (
                        VerificationStatus.USER_CONFIRMED
                    ),
                    "uncertainty_reason": None,
                },
                deep=True,
            )
        )

    return CanonicalInventory(
        items=updated_items
    )