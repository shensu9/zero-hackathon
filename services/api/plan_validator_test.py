from plan_schemas import (
    CapabilityUse,
    PhysicalPlan,
    PlanStep,
)
from plan_validator import (
    PlanValidationError,
    validate_zero_plan,
)
from schemas import (
    CertaintyLevel,
    EvidenceBasis,
    ObjectAffordance,
    ObjectDNA,
    ObjectDNAResponse,
)


books_dna = ObjectDNA(
    item_id="books_01",
    physical_traits=[],
    affordances=[
        ObjectAffordance(
            capability="stack",
            description="Books can be stacked.",
            evidence_basis=EvidenceBasis.COMMON_PROPERTY,
            certainty=CertaintyLevel.HIGH,
        ),
        ObjectAffordance(
            capability="elevate",
            description="A book stack can raise an object.",
            evidence_basis=EvidenceBasis.COMMON_PROPERTY,
            certainty=CertaintyLevel.HIGH,
        ),
        ObjectAffordance(
            capability="provide_surface",
            description="A book provides a flat surface.",
            evidence_basis=EvidenceBasis.COMMON_PROPERTY,
            certainty=CertaintyLevel.HIGH,
        ),
    ],
    unknown_properties=[],
    caution_notes=[],
)


spray_bottle_dna = ObjectDNA(
    item_id="spray_bottles_01",
    physical_traits=[],
    affordances=[
        ObjectAffordance(
            capability="contain",
            description="Can hold liquid.",
            evidence_basis=EvidenceBasis.COMMON_PROPERTY,
            certainty=CertaintyLevel.HIGH,
        ),
        ObjectAffordance(
            capability="dispense_liquid",
            description="Can dispense liquid.",
            evidence_basis=EvidenceBasis.COMMON_PROPERTY,
            certainty=CertaintyLevel.HIGH,
        ),
        ObjectAffordance(
            capability="reposition",
            description="Can be moved by hand.",
            evidence_basis=EvidenceBasis.COMMON_PROPERTY,
            certainty=CertaintyLevel.HIGH,
        ),
    ],
    unknown_properties=[
        "current liquid contents",
    ],
    caution_notes=[
        "Identify the current liquid contents before reuse.",
    ],
)


object_dna = ObjectDNAResponse(
    objects=[
        books_dna,
        spray_bottle_dna,
    ]
)


valid_item_ids = {
    "books_01",
    "spray_bottles_01",
}


# ---------------------------------------------------------------------------
# VALID CASE
# ---------------------------------------------------------------------------


valid_plan = PhysicalPlan(
    title="Valid book riser",
    summary="Use books to raise a small object.",
    item_ids_used=[
        "books_01",
    ],
    steps=[
        PlanStep(
            order=1,
            action="Stack the books to raise the object.",
            item_ids=[
                "books_01",
            ],
            capability_uses=[
                CapabilityUse(
                    item_id="books_01",
                    capability="stack",
                    purpose="Create a stable stack.",
                ),
                CapabilityUse(
                    item_id="books_01",
                    capability="elevate",
                    purpose="Raise the object.",
                ),
            ],
            why_it_helps="Creates a simple elevated platform.",
        )
    ],
    assumptions=[],
    unresolved_risks=[],
    constraint_check=[
        "Uses only available inventory.",
    ],
)


validate_zero_plan(
    valid_plan,
    object_dna,
    valid_item_ids,
)

print("VALID PLAN: passed")


# ---------------------------------------------------------------------------
# INVALID CASE
# ---------------------------------------------------------------------------


invalid_plan = PhysicalPlan(
    title="Invalid spray bottle weight",
    summary="Attempt to use spray bottles as weights.",
    item_ids_used=[
        "spray_bottles_01",
    ],
    steps=[
        PlanStep(
            order=1,
            action="Use spray bottles as weights.",
            item_ids=[
                "spray_bottles_01",
            ],
            capability_uses=[
                CapabilityUse(
                    item_id="spray_bottles_01",
                    capability="provide_weight",
                    purpose="Hold material down.",
                )
            ],
            why_it_helps="Attempts to stabilize another object.",
        )
    ],
    assumptions=[],
    unresolved_risks=[],
    constraint_check=[
        "Uses only available inventory.",
    ],
)


try:
    validate_zero_plan(
        invalid_plan,
        object_dna,
        valid_item_ids,
    )

    raise RuntimeError(
        "TEST FAILURE: invalid plan was incorrectly accepted."
    )

except PlanValidationError as error:
    print("INVALID PLAN: correctly rejected")
    print(error)