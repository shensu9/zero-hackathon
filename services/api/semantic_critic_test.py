from plan_schemas import (
    CapabilityUse,
    PhysicalPlan,
    PlanStep,
)
from schemas import (
    CanonicalInventory,
    CertaintyLevel,
    EvidenceBasis,
    InventoryItem,
    ObjectAffordance,
    ObjectDNA,
    ObjectDNAResponse,
    PhysicalTrait,
    VerificationStatus,
)
from semantic_critic import audit_plan_semantics


inventory = CanonicalInventory(
    items=[
        InventoryItem(
            id="office_chair_01",
            name="office chair",
            description="Black wheeled office chair.",
            location_hint="test environment",
            source_confidence=1.0,
            verification_status=VerificationStatus.USER_CONFIRMED,
            uncertainty_reason=None,
        ),
        InventoryItem(
            id="blanket_01",
            name="blanket",
            description="Large thick blanket.",
            location_hint="test environment",
            source_confidence=1.0,
            verification_status=VerificationStatus.USER_CONFIRMED,
            uncertainty_reason=None,
        ),
        InventoryItem(
            id="books_01",
            name="books",
            description="Stack of books.",
            location_hint="test environment",
            source_confidence=1.0,
            verification_status=VerificationStatus.USER_CONFIRMED,
            uncertainty_reason=None,
        ),
    ]
)


object_dna = ObjectDNAResponse(
    objects=[
        ObjectDNA(
            item_id="office_chair_01",
            physical_traits=[],
            affordances=[
                ObjectAffordance(
                    capability="support",
                    description="Can support a seated person.",
                    evidence_basis=EvidenceBasis.COMMON_PROPERTY,
                    certainty=CertaintyLevel.HIGH,
                ),
                ObjectAffordance(
                    capability="reposition",
                    description="Can be moved on its wheels.",
                    evidence_basis=EvidenceBasis.VISUALLY_OBSERVED,
                    certainty=CertaintyLevel.HIGH,
                ),
            ],
            unknown_properties=[],
            caution_notes=[],
        ),

        ObjectDNA(
            item_id="blanket_01",
            physical_traits=[
                PhysicalTrait(
                    trait="soft",
                    evidence_basis=EvidenceBasis.COMMON_PROPERTY,
                    certainty=CertaintyLevel.HIGH,
                    note="Blanket is soft fabric.",
                )
            ],
            affordances=[
                ObjectAffordance(
                    capability="cover",
                    description="Can cover a large area.",
                    evidence_basis=EvidenceBasis.COMMON_PROPERTY,
                    certainty=CertaintyLevel.HIGH,
                ),
                ObjectAffordance(
                    capability="cushion",
                    description="Can provide soft padding.",
                    evidence_basis=EvidenceBasis.COMMON_PROPERTY,
                    certainty=CertaintyLevel.HIGH,
                ),
            ],
            unknown_properties=[],
            caution_notes=[],
        ),

        ObjectDNA(
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
                    description="Book stack can raise an object.",
                    evidence_basis=EvidenceBasis.COMMON_PROPERTY,
                    certainty=CertaintyLevel.HIGH,
                ),
                ObjectAffordance(
                    capability="provide_surface",
                    description="Top book provides a flat surface.",
                    evidence_basis=EvidenceBasis.COMMON_PROPERTY,
                    certainty=CertaintyLevel.HIGH,
                ),
            ],
            unknown_properties=[],
            caution_notes=[],
        ),
    ]
)


bad_plan = PhysicalPlan(
    title="Well-lit tabletop photography setup",

    summary=(
        "Use a tabletop, books, and a blanket to create "
        "a well-lit product photography area."
    ),

    item_ids_used=[
        "office_chair_01",
        "blanket_01",
        "books_01",
    ],

    steps=[
        PlanStep(
            order=1,
            action="Place the books on the tabletop.",
            item_ids=[
                "books_01",
            ],
            capability_uses=[
                CapabilityUse(
                    item_id="books_01",
                    capability="stack",
                    purpose="Create a stack.",
                ),
                CapabilityUse(
                    item_id="books_01",
                    capability="elevate",
                    purpose="Raise the product.",
                ),
            ],
            why_it_helps=(
                "Creates a stable elevated platform."
            ),
        ),

        PlanStep(
            order=2,
            action=(
                "Lay the blanket down as a non-slip "
                "surface for the product."
            ),
            item_ids=[
                "blanket_01",
            ],
            capability_uses=[
                CapabilityUse(
                    item_id="blanket_01",
                    capability="cushion",
                    purpose="Provide a soft layer.",
                )
            ],
            why_it_helps=(
                "The non-slip surface prevents movement."
            ),
        ),

        PlanStep(
            order=3,
            action=(
                "Move the chair until the setup is well-lit "
                "with minimal shadow."
            ),
            item_ids=[
                "office_chair_01",
            ],
            capability_uses=[
                CapabilityUse(
                    item_id="office_chair_01",
                    capability="reposition",
                    purpose="Change the setup position.",
                )
            ],
            why_it_helps=(
                "Creates even lighting for the photograph."
            ),
        ),
    ],

    assumptions=[],
    unresolved_risks=[],

    constraint_check=[
        "Budget remains $0.",
    ],
)


result = audit_plan_semantics(
    plan=bad_plan,
    goal=(
        "Create a $0 product photography setup "
        "without permanent modifications."
    ),
    inventory=inventory.items,
    object_dna=object_dna,
    external_resources=[
        "phone camera",
    ],
)


print(
    result.model_dump_json(
        indent=2
    )
)


if result.passed:
    raise RuntimeError(
        "TEST FAILURE: semantic critic accepted the intentionally bad plan."
    )


if not result.findings:
    raise RuntimeError(
        "TEST FAILURE: critic failed to identify any problems."
    )


print()
print("SEMANTIC CRITIC TEST: correctly rejected bad plan")