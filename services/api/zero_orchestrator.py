from collections.abc import Callable

from pydantic import BaseModel, Field

from object_dna_service import (
    generate_object_dna,
)
from plan_outcome_pipeline import (
    SafePlanOutcomeResult,
    generate_safe_plan_outcome,
)
from schemas import (
    CanonicalInventory,
    InventoryItem,
    ObjectDNAResponse,
    VerificationStatus,
)


class ZeroGoalRequest(BaseModel):
    """
    Product-facing input after perception/inventory confirmation.

    The future video walkthrough pipeline should eventually produce
    CanonicalInventory and feed it into this boundary.
    """

    goal: str = Field(
        min_length=1,
        max_length=2000,
    )

    inventory: CanonicalInventory

    external_resources: list[str] = Field(
        default_factory=list,
        max_length=10,
    )


class ZeroGoalResult(BaseModel):
    """
    Complete downstream ZERO result.

    pending_confirmation_item_ids are excluded from physical reasoning
    until the perception/inventory layer resolves them.
    """

    active_inventory: CanonicalInventory

    pending_confirmation_item_ids: list[str] = Field(
        default_factory=list,
    )

    object_dna: ObjectDNAResponse

    planning: SafePlanOutcomeResult


def _partition_inventory(
    inventory: CanonicalInventory,
) -> tuple[
    list[InventoryItem],
    list[str],
]:
    active_items = []

    pending_confirmation_ids = []

    for item in inventory.items:
        if (
            item.verification_status
            == VerificationStatus.NEEDS_CONFIRMATION
        ):
            pending_confirmation_ids.append(
                item.id
            )

            continue

        active_items.append(
            item
        )

    return (
        active_items,
        pending_confirmation_ids,
    )


def _generate_object_dna_for_inventory(
    inventory_items: list[InventoryItem],
) -> ObjectDNAResponse:
    objects = []

    for item in inventory_items:
        objects.append(
            generate_object_dna(
                item
            )
        )

    return ObjectDNAResponse(
        objects=objects
    )


def _validate_object_dna_coverage(
    *,
    inventory_items: list[InventoryItem],
    object_dna: ObjectDNAResponse,
) -> None:
    """
    A supplied/precomputed world model must correspond exactly to the
    active canonical inventory.

    This prevents stale DNA from another walkthrough or inventory from
    silently entering planning.
    """

    inventory_ids = [
        item.id
        for item in inventory_items
    ]

    dna_ids = [
        dna.item_id
        for dna in object_dna.objects
    ]

    if (
        len(set(inventory_ids))
        != len(inventory_ids)
    ):
        raise ValueError(
            "Active canonical inventory contains "
            "duplicate item IDs."
        )

    if (
        len(set(dna_ids))
        != len(dna_ids)
    ):
        raise ValueError(
            "Object DNA contains duplicate item IDs."
        )

    inventory_set = set(
        inventory_ids
    )

    dna_set = set(
        dna_ids
    )

    missing_dna = sorted(
        inventory_set
        - dna_set
    )

    extra_dna = sorted(
        dna_set
        - inventory_set
    )

    if missing_dna:
        raise ValueError(
            "Object DNA is missing active inventory "
            f"items: {missing_dna}"
        )

    if extra_dna:
        raise ValueError(
            "Object DNA contains items that are not "
            f"in active inventory: {extra_dna}"
        )


def run_zero_goal(
    request: ZeroGoalRequest,
    *,
    object_dna: ObjectDNAResponse | None = None,
    outcome_runner: Callable = (
        generate_safe_plan_outcome
    ),
) -> ZeroGoalResult:
    """
    Main downstream ZERO orchestration boundary.

    Flow:

    CanonicalInventory
        ->
    remove NEEDS_CONFIRMATION observations from physical reasoning
        ->
    validated Object DNA
        ->
    guarded outcome pipeline
        ->
    SOLVED / CONDITIONAL / NEEDS_CONFIRMATION /
    CANNOT_SAFELY_SOLVE

    object_dna may be injected when a validated/cached world model
    already exists. This is useful for persistent sessions and tests.
    """

    (
        active_items,
        pending_confirmation_ids,
    ) = _partition_inventory(
        request.inventory
    )

    active_inventory = CanonicalInventory(
        items=active_items
    )

    if object_dna is None:
        object_dna = (
            _generate_object_dna_for_inventory(
                active_items
            )
        )

    _validate_object_dna_coverage(
        inventory_items=active_items,
        object_dna=object_dna,
    )

    planning = outcome_runner(
        goal=request.goal,
        inventory=active_items,
        object_dna=object_dna,
        external_resources=(
            request.external_resources
        ),
    )

    return ZeroGoalResult(
        active_inventory=active_inventory,

        pending_confirmation_item_ids=(
            pending_confirmation_ids
        ),

        object_dna=object_dna,

        planning=planning,
    )