from copy import deepcopy
from typing import Any


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

    # Safe redundant summary/default fields.
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