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
    One uncertain canonical inventory item worth asking the user about now.

    This is only a confirmation candidate.

    Its verification status remains NEEDS_CONFIRMATION until a separate,
    explicit human-confirmation step.
    """

    item: InventoryItem

    relevance: RelevanceLabel

    relevance_reason: str = Field(
        min_length=1,
        max_length=300,
    )


class GoalScopedConfirmationSelection(BaseModel):
    """
    Deterministic goal-scoped confirmation policy.

    candidates:
        NEEDS_CONFIRMATION items classified RELEVANT.
        These are worth asking the user about now.

    deferred_possible_item_ids:
        NEEDS_CONFIRMATION items classified POSSIBLY_RELEVANT.
        They remain unavailable to Object DNA/planning and are not asked
        about initially. A later bounded escalation policy may reconsider
        them if the current eligible inventory proves insufficient.

    not_relevant_pending_item_ids:
        NEEDS_CONFIRMATION items classified NOT_RELEVANT.
        They remain pending but are ignored for this goal.
    """

    candidates: list[
        GoalScopedConfirmationCandidate
    ]

    deferred_possible_item_ids: list[str] = Field(
        default_factory=list,
    )

    not_relevant_pending_item_ids: list[str] = Field(
        default_factory=list,
    )


def select_goal_scoped_confirmation_candidates(
    *,
    inventory: CanonicalInventory,
    relevance: GoalAwareInventoryResponse,
) -> GoalScopedConfirmationSelection:
    """
    Decide which uncertain inventory items should be confirmed NOW.

    Safety invariants:

    - Canonical inventory IDs must be unique.
    - Relevance output may contain only real NEEDS_CONFIRMATION IDs.
    - Relevance output may not contain duplicate IDs.
    - Every NEEDS_CONFIRMATION item must have exactly one relevance decision.
    - Only RELEVANT items become immediate confirmation candidates.
    - POSSIBLY_RELEVANT items are deferred rather than promoted.
    - NOT_RELEVANT items remain pending and unused.
    - AUTO_ACCEPTED / USER_CONFIRMED items are never confirmation candidates.
    - This function NEVER changes verification status.
    """

    inventory_by_id: dict[
        str,
        InventoryItem,
    ] = {}

    pending_items: list[
        InventoryItem
    ] = []

    for item in inventory.items:
        if item.id in inventory_by_id:
            raise ValueError(
                "Canonical inventory contains duplicate item ID: "
                f"{item.id}"
            )

        inventory_by_id[item.id] = item

        if (
            item.verification_status
            == VerificationStatus.NEEDS_CONFIRMATION
        ):
            pending_items.append(
                item
            )

    pending_ids = {
        item.id
        for item in pending_items
    }

    relevance_by_id = {}

    for relevance_item in relevance.items:
        item_id = relevance_item.item_id

        if item_id in relevance_by_id:
            raise ValueError(
                "Goal-aware relevance contains duplicate item ID: "
                f"{item_id}"
            )

        if item_id not in inventory_by_id:
            raise ValueError(
                "Goal-aware relevance contains an item ID that is not "
                "present in canonical inventory: "
                f"{item_id}"
            )

        if item_id not in pending_ids:
            raise ValueError(
                "Goal-aware relevance contains an item ID that is not "
                "a NEEDS_CONFIRMATION inventory item: "
                f"{item_id}"
            )

        relevance_by_id[
            item_id
        ] = relevance_item

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

    deferred_possible_item_ids: list[
        str
    ] = []

    not_relevant_pending_item_ids: list[
        str
    ] = []

    for item in pending_items:
        relevance_item = (
            relevance_by_id[item.id]
        )

        if (
            relevance_item.relevance
            == RelevanceLabel.RELEVANT
        ):
            candidates.append(
                GoalScopedConfirmationCandidate(
                    item=item,
                    relevance=(
                        relevance_item.relevance
                    ),
                    relevance_reason=(
                        relevance_item.reason
                    ),
                )
            )

            continue

        if (
            relevance_item.relevance
            == RelevanceLabel.POSSIBLY_RELEVANT
        ):
            deferred_possible_item_ids.append(
                item.id
            )

            continue

        if (
            relevance_item.relevance
            == RelevanceLabel.NOT_RELEVANT
        ):
            not_relevant_pending_item_ids.append(
                item.id
            )

            continue

        raise ValueError(
            "Unsupported goal relevance label for "
            f"{item.id}: {relevance_item.relevance}"
        )

    return GoalScopedConfirmationSelection(
        candidates=candidates,
        deferred_possible_item_ids=(
            deferred_possible_item_ids
        ),
        not_relevant_pending_item_ids=(
            not_relevant_pending_item_ids
        ),
    )