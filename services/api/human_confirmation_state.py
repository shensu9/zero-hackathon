from __future__ import annotations

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)

from schemas import (
    CanonicalInventory,
    InventoryItem,
    VerificationStatus,
)


class HumanItemCorrection(BaseModel):
    """
    Explicit user correction to model-derived identity metadata.

    The canonical inventory remains immutable. Corrections are applied only
    when reconstructing the session inventory.

    A correction may change human-facing identity fields only. It may never
    change the canonical item ID, model confidence, or verification status.
    """

    item_id: str = Field(
        min_length=1,
        max_length=100,
    )

    corrected_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    corrected_description: str | None = Field(
        default=None,
        min_length=1,
        max_length=300,
    )

    corrected_location_hint: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    user_note: str | None = Field(
        default=None,
        min_length=1,
        max_length=500,
    )

    @model_validator(
        mode="after"
    )
    def require_actual_correction(
        self,
    ):
        if (
            self.corrected_name is None
            and self.corrected_description is None
            and self.corrected_location_hint is None
        ):
            raise ValueError(
                "Human item correction must change at least "
                "one identity field."
            )

        return self


class PersistedHumanConfirmationState(BaseModel):
    """
    Persistent human-evidence delta for one exact canonical inventory.

    This does NOT duplicate or mutate CanonicalInventory.

    It records:

    - which source NEEDS_CONFIRMATION items the user explicitly confirmed
      as physically present
    - explicit user corrections to model-derived identity metadata

    inventory_sha256 binds this evidence to the exact source inventory.
    """

    inventory_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    confirmed_item_ids: list[str] = Field(
        default_factory=list,
    )

    item_corrections: list[
        HumanItemCorrection
    ] = Field(
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

        inventory_by_id[
            item.id
        ] = item

    return inventory_by_id


def validate_confirmation_state(
    *,
    inventory: CanonicalInventory,
    inventory_sha256: str,
    state: PersistedHumanConfirmationState,
) -> PersistedHumanConfirmationState:
    """
    Validate persisted human evidence against the exact source inventory.

    Safety invariants:

    - state must belong to this exact inventory fingerprint
    - confirmed IDs must be unique
    - every confirmed ID must exist in canonical inventory
    - every persisted confirmation must originate from an item that was
      NEEDS_CONFIRMATION in the source canonical inventory
    - correction item IDs must be unique
    - every correction must refer to an existing canonical item
    - corrections cannot mutate canonical IDs, confidence, or status
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

    seen_confirmed_ids: set[
        str
    ] = set()

    for item_id in (
        state.confirmed_item_ids
    ):
        if (
            item_id
            in seen_confirmed_ids
        ):
            raise ValueError(
                "Human confirmation state contains duplicate item ID: "
                f"{item_id}"
            )

        seen_confirmed_ids.add(
            item_id
        )

        if (
            item_id
            not in inventory_by_id
        ):
            raise ValueError(
                "Human confirmation state contains an item ID "
                "that is not present in canonical inventory: "
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
                "Persisted human confirmation refers to an item "
                "that was not NEEDS_CONFIRMATION in the source "
                f"inventory: {item_id}"
            )

    seen_correction_ids: set[
        str
    ] = set()

    for correction in (
        state.item_corrections
    ):
        item_id = (
            correction.item_id
        )

        if (
            item_id
            in seen_correction_ids
        ):
            raise ValueError(
                "Human confirmation state contains duplicate "
                f"correction item ID: {item_id}"
            )

        seen_correction_ids.add(
            item_id
        )

        if (
            item_id
            not in inventory_by_id
        ):
            raise ValueError(
                "Human item correction refers to an item ID "
                "that is not present in canonical inventory: "
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
    new_item_corrections: (
        list[
            HumanItemCorrection
        ]
        | None
    ) = None,
) -> PersistedHumanConfirmationState:
    """
    Merge new explicit user evidence into persisted state.

    Confirmed-ID order and correction order follow canonical inventory order.

    Re-confirming an already persisted ID is idempotent.

    A new correction for an item replaces an older correction for the same
    item, allowing later explicit user clarification to supersede earlier
    human evidence.

    Duplicate IDs inside one new input batch are rejected.
    """

    inventory_by_id = (
        _validate_canonical_inventory(
            inventory
        )
    )

    if existing_state is None:
        existing_ids: set[str] = (
            set()
        )

        corrections_by_id: dict[
            str,
            HumanItemCorrection,
        ] = {}

    else:
        validated_existing = (
            validate_confirmation_state(
                inventory=inventory,
                inventory_sha256=(
                    inventory_sha256
                ),
                state=existing_state,
            )
        )

        existing_ids = set(
            validated_existing
            .confirmed_item_ids
        )

        corrections_by_id = {
            correction.item_id:
                correction
            for correction
            in validated_existing
            .item_corrections
        }

    seen_new_ids: set[
        str
    ] = set()

    for item_id in (
        newly_confirmed_item_ids
    ):
        if (
            item_id
            in seen_new_ids
        ):
            raise ValueError(
                "New human confirmations contain duplicate "
                f"item ID: {item_id}"
            )

        seen_new_ids.add(
            item_id
        )

        if (
            item_id
            not in inventory_by_id
        ):
            raise ValueError(
                "New human confirmation contains an item ID "
                "that is not present in canonical inventory: "
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
                "New human confirmation refers to an item "
                "that is not NEEDS_CONFIRMATION in the source "
                f"inventory: {item_id}"
            )

    new_corrections = (
        []
        if new_item_corrections is None
        else new_item_corrections
    )

    seen_new_correction_ids: set[
        str
    ] = set()

    for correction in (
        new_corrections
    ):
        item_id = (
            correction.item_id
        )

        if (
            item_id
            in seen_new_correction_ids
        ):
            raise ValueError(
                "New human corrections contain duplicate "
                f"item ID: {item_id}"
            )

        seen_new_correction_ids.add(
            item_id
        )

        if (
            item_id
            not in inventory_by_id
        ):
            raise ValueError(
                "New human correction refers to an item ID "
                "that is not present in canonical inventory: "
                f"{item_id}"
            )

        corrections_by_id[
            item_id
        ] = correction

    combined_ids = (
        existing_ids
        | seen_new_ids
    )

    ordered_ids = [
        item.id
        for item in inventory.items
        if item.id in combined_ids
    ]

    ordered_corrections = [
        corrections_by_id[
            item.id
        ]
        for item
        in inventory.items
        if (
            item.id
            in corrections_by_id
        )
    ]

    merged_state = (
        PersistedHumanConfirmationState(
            inventory_sha256=(
                inventory_sha256
            ),
            confirmed_item_ids=(
                ordered_ids
            ),
            item_corrections=(
                ordered_corrections
            ),
        )
    )

    return validate_confirmation_state(
        inventory=inventory,
        inventory_sha256=(
            inventory_sha256
        ),
        state=merged_state,
    )


def apply_confirmation_state(
    *,
    inventory: CanonicalInventory,
    inventory_sha256: str,
    state: PersistedHumanConfirmationState,
) -> CanonicalInventory:
    """
    Reconstruct a session inventory from immutable canonical inventory plus
    persisted explicit human evidence.

    The source CanonicalInventory is never mutated.

    Identity corrections are applied to session copies only.

    Only persisted confirmed IDs are promoted:
        NEEDS_CONFIRMATION -> USER_CONFIRMED

    A corrected but unconfirmed NEEDS_CONFIRMATION item therefore remains
    excluded from Object DNA and planning.
    """

    validated_state = (
        validate_confirmation_state(
            inventory=inventory,
            inventory_sha256=(
                inventory_sha256
            ),
            state=state,
        )
    )

    confirmed_ids = set(
        validated_state
        .confirmed_item_ids
    )

    corrections_by_id = {
        correction.item_id:
            correction
        for correction
        in validated_state
        .item_corrections
    }

    updated_items: list[
        InventoryItem
    ] = []

    for item in inventory.items:
        updates = {}

        correction = (
            corrections_by_id.get(
                item.id
            )
        )

        if correction is not None:
            if (
                correction
                .corrected_name
                is not None
            ):
                updates[
                    "name"
                ] = (
                    correction
                    .corrected_name
                )

            if (
                correction
                .corrected_description
                is not None
            ):
                updates[
                    "description"
                ] = (
                    correction
                    .corrected_description
                )

            if (
                correction
                .corrected_location_hint
                is not None
            ):
                updates[
                    "location_hint"
                ] = (
                    correction
                    .corrected_location_hint
                )

        if (
            item.id
            in confirmed_ids
        ):
            updates[
                "verification_status"
            ] = (
                VerificationStatus
                .USER_CONFIRMED
            )

            updates[
                "uncertainty_reason"
            ] = None

        if not updates:
            updated_items.append(
                item.model_copy(
                    deep=True
                )
            )

            continue

        updated_items.append(
            item.model_copy(
                update=updates,
                deep=True,
            )
        )

    return CanonicalInventory(
        items=updated_items
    )