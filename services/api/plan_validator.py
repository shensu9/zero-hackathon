from plan_schemas import PhysicalPlan
from schemas import (
    CapabilityType,
    CertaintyLevel,
    ObjectDNAResponse,
)


class PlanValidationError(ValueError):
    pass



def normalize_plan_item_ids(
    plan: PhysicalPlan,
) -> PhysicalPlan:
    """
    Derive the plan-level item_ids_used field from the actual step usage.

    Step item_ids are the source of truth. This avoids treating a redundant
    summary-field omission by the model as a planning failure.
    """

    item_ids = sorted({
        item_id
        for step in plan.steps
        for item_id in step.item_ids
    })

    return plan.model_copy(
        update={
            "item_ids_used": item_ids,
        }
    )


def validate_inventory_grounding(
    plan: PhysicalPlan,
    valid_item_ids: set[str],
) -> PhysicalPlan:
    """
    Verify that the plan references only real inventory items.
    """

    errors: list[str] = []

    top_level_ids = set(
        plan.item_ids_used
    )

    invented_top_level = (
        top_level_ids
        - valid_item_ids
    )

    if invented_top_level:
        errors.append(
            "Plan item_ids_used contains unknown items: "
            f"{sorted(invented_top_level)}"
        )

    step_item_ids: set[str] = set()

    for step in plan.steps:
        current_ids = set(
            step.item_ids
        )

        step_item_ids.update(
            current_ids
        )

        invented_step_ids = (
            current_ids
            - valid_item_ids
        )

        if invented_step_ids:
            errors.append(
                f"Step {step.order} references unknown items: "
                f"{sorted(invented_step_ids)}"
            )

    if top_level_ids != step_item_ids:
        errors.append(
            "item_ids_used must exactly match the inventory "
            "items referenced by plan steps. "
            f"Top-level: {sorted(top_level_ids)} | "
            f"Steps: {sorted(step_item_ids)}"
        )

    if errors:
        raise PlanValidationError(
            " | ".join(errors)
        )

    return plan


def validate_capability_grounding(
    plan: PhysicalPlan,
    object_dna: ObjectDNAResponse,
) -> PhysicalPlan:
    """
    Verify that every physical use of an inventory item is backed
    by an affordance that exists in that item's validated Object DNA.

    Low-certainty affordances are not allowed to authorize a
    physical action in ZERO V1.
    """

    errors: list[str] = []

    capability_map: dict[
        str,
        dict[CapabilityType, CertaintyLevel],
    ] = {}

    for dna in object_dna.objects:
        capability_map[dna.item_id] = {
            affordance.capability: affordance.certainty
            for affordance in dna.affordances
        }

    for step in plan.steps:
        step_items = set(
            step.item_ids
        )

        # A physical inventory item may not participate in a step
        # without explaining which Object DNA capability authorizes it.
        if step_items and not step.capability_uses:
            errors.append(
                f"Step {step.order} uses inventory items but cites "
                "no Object DNA capabilities."
            )
            continue

        capability_covered_items: set[str] = set()

        for use in step.capability_uses:
            if use.item_id not in step_items:
                errors.append(
                    f"Step {step.order} cites capability "
                    f"{use.capability.value} for {use.item_id}, "
                    "but that item is not listed in step.item_ids."
                )
                continue

            if use.item_id not in capability_map:
                errors.append(
                    f"Step {step.order} references {use.item_id}, "
                    "but no validated Object DNA exists for it."
                )
                continue

            available_capabilities = capability_map[
                use.item_id
            ]

            if use.capability not in available_capabilities:
                errors.append(
                    f"Step {step.order}: "
                    f"{use.item_id}.{use.capability.value} "
                    "is NOT supported by validated Object DNA."
                )
                continue

            certainty = available_capabilities[
                use.capability
            ]

            if certainty == CertaintyLevel.LOW:
                errors.append(
                    f"Step {step.order}: "
                    f"{use.item_id}.{use.capability.value} "
                    "has LOW certainty and cannot authorize "
                    "a physical action in ZERO V1."
                )
                continue

            capability_covered_items.add(
                use.item_id
            )

        missing_capability_grounding = (
            step_items
            - capability_covered_items
        )

        if missing_capability_grounding:
            errors.append(
                f"Step {step.order} uses items without valid "
                "capability grounding: "
                f"{sorted(missing_capability_grounding)}"
            )

    if errors:
        raise PlanValidationError(
            " | ".join(errors)
        )

    return plan


def validate_zero_plan(
    plan: PhysicalPlan,
    object_dna: ObjectDNAResponse,
    valid_item_ids: set[str],
) -> PhysicalPlan:
    """
    Full deterministic ZERO plan validation.
    """

    plan = validate_inventory_grounding(
        plan,
        valid_item_ids,
    )

    plan = validate_capability_grounding(
        plan,
        object_dna,
    )

    return plan