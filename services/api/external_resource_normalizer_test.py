from plan_normalizer import (
    normalize_external_resource_ids,
)
from plan_schemas import PhysicalPlan
from plan_validator import (
    normalize_plan_item_ids,
)


plan = PhysicalPlan.model_validate(
    {
        "title":
            "External resource normalization test",

        "summary":
            "Test structural cleanup only.",

        "item_ids_used": [
            "books_01",
            "small lightweight object",
            "table_99",
        ],

        "steps": [
            {
                "order": 1,

                "action":
                    "Place the small lightweight object on the books.",

                "item_ids": [
                    "books_01",
                    "small lightweight object",
                ],

                "capability_uses": [],

                "why_it_helps":
                    "Tests a valid external resource.",
            },
            {
                "order": 2,

                "action":
                    "Move the setup onto table_99.",

                "item_ids": [
                    "table_99",
                ],

                "capability_uses": [],

                "why_it_helps":
                    "Tests that unknown resources are preserved.",
            },
        ],

        "assumptions": [],
        "unresolved_risks": [],
        "constraint_check": [],
    }
)


normalized = normalize_external_resource_ids(
    plan,
    (
        "small lightweight object",
    ),
)

normalized = normalize_plan_item_ids(
    normalized
)


assert (
    "small lightweight object"
    not in normalized.item_ids_used
)

assert (
    "small lightweight object"
    not in normalized.steps[0].item_ids
)

# Unknown/hallucinated resources MUST remain so validators can reject them.
assert (
    "table_99"
    in normalized.item_ids_used
)

assert (
    "table_99"
    in normalized.steps[1].item_ids
)

# Physical language must remain untouched.
assert (
    normalized.steps[0].action
    == "Place the small lightweight object on the books."
)


print(
    "EXTERNAL RESOURCE NORMALIZER TEST: passed"
)

print(
    "item_ids_used:",
    normalized.item_ids_used,
)