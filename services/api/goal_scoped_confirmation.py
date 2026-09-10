from pydantic import BaseModel, Field

from schemas import (
    CanonicalInventory,
    GoalAwareInventoryResponse,
    InventoryItem,
    RelevanceLabel,
    VerificationStatus,
)


class GoalScopedConfirmationCandidate(BaseModel):
    """
    One uncertain canonical inventory item that is worth asking the user
    about for the current goal.

    This is only a confirmation candidate. Its verification status remains
    NEEDS_CONFIRMATION until a separate explicit human-confirmation step.
    """

    item: InventoryItem

    relevance: RelevanceLabel

    relevance_reason: str = Field(
        min_length=1,
        max_length=300,
    )


class GoalScopedConfirmationSelection(BaseModel):
    """
    Deterministic result of applying goal relevance to pending inventory.

    candidates:
        NEEDS_CONFIRMATION items whose relevance is RELEVANT or
        POSSIBLY_RELEVANT.

    not_selected_pending_item_ids:
        NEEDS_CONFIRMATION items judged NOT_RELEVANT to the current goal.
        They remain pending and must not enter Object DNA/planning.
    """

    candidates: list[GoalScopedConfirmationCandidate]

    not_selected_pending_item_ids: list[str] = Field(
        default_factory=list,
    )


def select_goal_scoped_confirmation_candidates(
    *,
    inventory: CanonicalInventory,
    relevance: GoalAwareInventoryResponse,
) -> GoalScopedConfirmationSelection:
    """
    Select which uncertain inventory items are worth asking the user about.

    Safety invariants:

    - Only real CanonicalInventory IDs may appear in relevance output.
    - Relevance output may not contain duplicate item IDs.
    - Every NEEDS_CONFIRMATION item must have a relevance decision.
    - AUTO_ACCEPTED / USER_CONFIRMED items are never confirmation candidates.
    - This function NEVER changes verification status.
    - NOT_RELEVANT pending items remain NEEDS_CONFIRMATION.
    """

    inventory_by_id: dict[str, InventoryItem] = {}

    for item in inventory.items:
        if item.id in inventory_by_id:
            raise ValueError(
                "Canonical inventory contains duplicate item ID: "
                f"{item.id}"
            )

        inventory_by_id[item.id] = item

    relevance_by_id = {}

    for relevance_item in relevance.items:
        if relevance_item.item_id in relevance_by_id:
            raise ValueError(
                "Goal-aware relevance contains duplicate item ID: "
                f"{relevance_item.item_id}"
            )

        if relevance_item.item_id not in inventory_by_id:
            raise ValueError(
                "Goal-aware relevance contains an item ID that is not "
                "present in canonical inventory: "
                f"{relevance_item.item_id}"
            )

        relevance_by_id[
            relevance_item.item_id
        ] = relevance_item

    pending_items = [
        item
        for item in inventory.items
        if (
            item.verification_status
            == VerificationStatus.NEEDS_CONFIRMATION
        )
    ]

    missing_pending_ids = [
        item.id
        for item in pending_items
        if item.id not in relevance_by_id
    ]

    if missing_pending_ids:
        raise ValueError(
            "Goal-aware relevance is missing NEEDS_CONFIRMATION "
            f"inventory items: {sorted(missing_pending_ids)}"
        )

    candidates: list[
        GoalScopedConfirmationCandidate
    ] = []

    not_selected_pending_item_ids: list[str] = []

    for item in pending_items:
        relevance_item = relevance_by_id[item.id]

        if relevance_item.relevance in {
            RelevanceLabel.RELEVANT,
            RelevanceLabel.POSSIBLY_RELEVANT,
        }:
            candidates.append(
                GoalScopedConfirmationCandidate(
                    item=item,
                    relevance=relevance_item.relevance,
                    relevance_reason=relevance_item.reason,
                )
            )

            continue

        not_selected_pending_item_ids.append(
            item.id
        )

    return GoalScopedConfirmationSelection(
        candidates=candidates,
        not_selected_pending_item_ids=(
            not_selected_pending_item_ids
        ),
    )