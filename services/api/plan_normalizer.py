from copy import deepcopy
from typing import Any

from plan_schemas import PhysicalPlan


def normalize_plan_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize harmless structural omissions in model-generated plans.

    The JSON steps array is the source of truth for execution order,
    so step.order is derived deterministically from array position.

    This function does NOT repair semantic or physical mistakes.
    """

    data = deepcopy(payload)

    steps = data.get("steps")

    if isinstance(steps, list):
        for index, step in enumerate(
            steps,
            start=1,
        ):
            if not isinstance(
                step,
                dict,
            ):
                continue

            # Array position is authoritative.
            step["order"] = index

            # These fields have safe empty defaults.
            step.setdefault(
                "item_ids",
                [],
            )

            step.setdefault(
                "capability_uses",
                [],
            )

    data.setdefault(
        "item_ids_used",
        [],
    )

    data.setdefault(
        "assumptions",
        [],
    )

    data.setdefault(
        "unresolved_risks",
        [],
    )

    data.setdefault(
        "constraint_check",
        [],
    )

    return data


def _resource_key(
    value: str,
) -> str:
    """
    Normalize a human-readable external-resource name for exact matching.

    This is intentionally conservative:
    only case/whitespace differences are ignored.
    """

    return " ".join(
        value
        .strip()
        .casefold()
        .split()
    )


def normalize_external_resource_ids(
    plan: PhysicalPlan,
    external_resources,
) -> PhysicalPlan:
    """
    Remove explicit external resources from inventory-ID fields.

    Example:

        action:
            "Place the small lightweight object on the books."

        item_ids:
            ["books_01", "small lightweight object"]

    becomes:

        item_ids:
            ["books_01"]

    The action remains unchanged.

    IMPORTANT:
    - Only explicitly declared external resources are removed.
    - Unknown/hallucinated objects are NOT removed.
    - capability_uses are NOT altered.
    - No semantic or physical claim is repaired.
    """

    external_keys = {
        _resource_key(
            str(resource)
        )
        for resource in external_resources
        if str(resource).strip()
    }

    if not external_keys:
        return plan.model_copy(
            deep=True
        )

    normalized = plan.model_copy(
        deep=True
    )

    normalized.item_ids_used = [
        item_id
        for item_id in normalized.item_ids_used
        if (
            _resource_key(item_id)
            not in external_keys
        )
    ]

    for step in normalized.steps:
        step.item_ids = [
            item_id
            for item_id in step.item_ids
            if (
                _resource_key(item_id)
                not in external_keys
            )
        ]

    return normalized