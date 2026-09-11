from pydantic import BaseModel, Field

from goal_scoped_confirmation import (
    GoalScopedConfirmationSelection,
)
from schemas import (
    CanonicalInventory,
    InventoryItem,
    VerificationStatus,
)


class HumanConfirmationResult(BaseModel):
    """
    Result of applying explicit positive user confirmations.

    Only exact items that were presented as immediate confirmation
    candidates may be promoted to USER_CONFIRMED.
    """

    inventory: CanonicalInventory

    confirmed_item_ids: list[str] = Field(
        default_factory=list,
    )

    unconfirmed_candidate_item_ids: list[str] = Field(
        default_factory=list,
    )


def apply_explicit_user_confirmations(
    *,
    inventory: CanonicalInventory,
    selection: GoalScopedConfirmationSelection,
    confirmed_item_ids: list[str],
) -> HumanConfirmationResult:
    """
    Promote explicitly confirmed immediate candidates to USER_CONFIRMED.

    Safety invariants:

    - Canonical inventory item IDs must be unique.
    - Selection candidate IDs must be unique.
    - Every selection candidate must exist in canonical inventory.
    - Every selection candidate must still be NEEDS_CONFIRMATION.
    - confirmed_item_ids must be unique.
    - A confirmed ID must have been presented in selection.candidates.
    - No deferred or not-relevant pending item may be promoted here.
    - AUTO_ACCEPTED / USER_CONFIRMED items may not be re-confirmed here.
    - Input CanonicalInventory is not mutated.
    - Item ordering is preserved.
    - No model confidence or relevance label can perform confirmation.
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

    candidate_ids: list[str] = []
    candidate_id_set: set[str] = set()

    for candidate in selection.candidates:
        item_id = candidate.item.id

        if item_id in candidate_id_set:
            raise ValueError(
                "Confirmation selection contains duplicate candidate ID: "
                f"{item_id}"
            )

        if item_id not in inventory_by_id:
            raise ValueError(
                "Confirmation selection contains an item ID that is not "
                "present in canonical inventory: "
                f"{item_id}"
            )

        canonical_item = inventory_by_id[item_id]

        if (
            canonical_item.verification_status
            != VerificationStatus.NEEDS_CONFIRMATION
        ):
            raise ValueError(
                "Confirmation selection contains an item that is not "
                "currently NEEDS_CONFIRMATION: "
                f"{item_id}"
            )

        candidate_ids.append(
            item_id
        )

        candidate_id_set.add(
            item_id
        )

    seen_confirmed_ids: set[str] = set()

    for item_id in confirmed_item_ids:
        if item_id in seen_confirmed_ids:
            raise ValueError(
                "Explicit user confirmation contains duplicate item ID: "
                f"{item_id}"
            )

        seen_confirmed_ids.add(
            item_id
        )

        if item_id not in candidate_id_set:
            raise ValueError(
                "Explicit user confirmation contains an item that was not "
                "presented as an immediate confirmation candidate: "
                f"{item_id}"
            )

    updated_items: list[
        InventoryItem
    ] = []

    for item in inventory.items:
        if item.id not in seen_confirmed_ids:
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

    unconfirmed_candidate_item_ids = [
        item_id
        for item_id in candidate_ids
        if item_id not in seen_confirmed_ids
    ]

    return HumanConfirmationResult(
        inventory=CanonicalInventory(
            items=updated_items
        ),
        confirmed_item_ids=[
            item_id
            for item_id in candidate_ids
            if item_id in seen_confirmed_ids
        ],
        unconfirmed_candidate_item_ids=(
            unconfirmed_candidate_item_ids
        ),
    )