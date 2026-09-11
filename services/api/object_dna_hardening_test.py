from object_dna_sanitizer import (
    sanitize_object_dna,
)
from object_dna_validator import (
    ObjectDNAValidationError,
    validate_object_dna,
)
from schemas import (
    CapabilityType,
    CertaintyLevel,
    EvidenceBasis,
    ObjectAffordance,
    ObjectDNA,
    PhysicalTrait,
    PhysicalTraitType,
)


def make_trait(
    trait: PhysicalTraitType,
) -> PhysicalTrait:
    return PhysicalTrait(
        trait=trait,
        evidence_basis=EvidenceBasis.COMMON_PROPERTY,
        certainty=CertaintyLevel.HIGH,
        note=f"Test trait: {trait.value}.",
    )


def make_affordance(
    capability: CapabilityType,
) -> ObjectAffordance:
    return ObjectAffordance(
        capability=capability,
        description=f"Test capability: {capability.value}.",
        evidence_basis=EvidenceBasis.COMMON_PROPERTY,
        certainty=CertaintyLevel.MEDIUM,
    )


def expect_validation_error(
    dna: ObjectDNA,
    expected_text: str,
) -> None:
    try:
        validate_object_dna(
            dna
        )

    except ObjectDNAValidationError as exc:
        if expected_text not in str(exc):
            raise AssertionError(
                "Validator failed for the expected reason, "
                "but the expected message was not present.\n"
                f"Expected: {expected_text}\n"
                f"Actual: {exc}"
            )

        return

    raise AssertionError(
        "Expected ObjectDNAValidationError was not raised."
    )


def test_electrical_requires_condition_unknown() -> None:
    dna = ObjectDNA(
        item_id="monitor_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.ELECTRICAL
            ),
        ],
        affordances=[],
        unknown_properties=[
            "electrical rating",
        ],
        caution_notes=[
            "Verify electrical rating and condition before reuse.",
        ],
    )

    expect_validation_error(
        dna,
        "unknown electrical condition",
    )

    print(
        "ELECTRICAL CONDITION UNKNOWN TEST: passed"
    )


def test_container_requires_unknown_contents() -> None:
    dna = ObjectDNA(
        item_id="box_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.HOLLOW
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.CONTAIN
            ),
        ],
        unknown_properties=[],
        caution_notes=[
            "Check current contents before repurposing the container.",
        ],
    )

    expect_validation_error(
        dna,
        "unknown current contents",
    )

    print(
        "CONTAINER CONTENTS UNKNOWN TEST: passed"
    )


def test_container_requires_contents_caution() -> None:
    dna = ObjectDNA(
        item_id="box_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.HOLLOW
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.CONTAIN
            ),
        ],
        unknown_properties=[
            "current contents",
        ],
        caution_notes=[],
    )

    expect_validation_error(
        dna,
        "inspect current contents before reuse",
    )

    print(
        "CONTAINER CONTENTS CAUTION TEST: passed"
    )


def test_support_requires_load_unknown() -> None:
    dna = ObjectDNA(
        item_id="platform_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.SUPPORT
            ),
        ],
        unknown_properties=[],
        caution_notes=[
            "Verify stability before reuse.",
        ],
    )

    expect_validation_error(
        dna,
        "unknown load-bearing capacity",
    )

    print(
        "SUPPORT LOAD UNKNOWN TEST: passed"
    )


def test_support_requires_stability_or_load_caution() -> None:
    dna = ObjectDNA(
        item_id="platform_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.SUPPORT
            ),
        ],
        unknown_properties=[
            "load-bearing capacity",
        ],
        caution_notes=[],
    )

    expect_validation_error(
        dna,
        "stability/load caution",
    )

    print(
        "SUPPORT CAUTION TEST: passed"
    )


def test_elevate_uses_same_load_guardrail() -> None:
    dna = ObjectDNA(
        item_id="riser_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.ELEVATE
            ),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    expect_validation_error(
        dna,
        "unknown load-bearing capacity",
    )

    print(
        "ELEVATE LOAD GUARDRAIL TEST: passed"
    )


def test_stack_requires_stackable_trait() -> None:
    dna = ObjectDNA(
        item_id="box_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.STACK
            ),
        ],
        unknown_properties=[
            "stacking stability",
        ],
        caution_notes=[
            "Verify stacking stability before reuse.",
        ],
    )

    expect_validation_error(
        dna,
        "stack requires a grounded stackable trait",
    )

    print(
        "STACKABLE TRAIT REQUIREMENT TEST: passed"
    )


def test_stack_requires_stability_unknown() -> None:
    dna = ObjectDNA(
        item_id="box_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.STACKABLE
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.STACK
            ),
        ],
        unknown_properties=[],
        caution_notes=[
            "Verify stacking stability before reuse.",
        ],
    )

    expect_validation_error(
        dna,
        "unknown stacking stability",
    )

    print(
        "STACK STABILITY UNKNOWN TEST: passed"
    )


def test_stack_requires_stability_caution() -> None:
    dna = ObjectDNA(
        item_id="box_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.STACKABLE
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.STACK
            ),
        ],
        unknown_properties=[
            "stacking stability",
        ],
        caution_notes=[],
    )

    expect_validation_error(
        dna,
        "stacking stability caution",
    )

    print(
        "STACK STABILITY CAUTION TEST: passed"
    )


def test_sanitizer_repairs_box_uncertainties() -> None:
    dna = ObjectDNA(
        item_id="box_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
            make_trait(
                PhysicalTraitType.HOLLOW
            ),
            make_trait(
                PhysicalTraitType.STACKABLE
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.CONTAIN
            ),
            make_affordance(
                CapabilityType.SUPPORT
            ),
            make_affordance(
                CapabilityType.ELEVATE
            ),
            make_affordance(
                CapabilityType.STACK
            ),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    assert (
        "current contents"
        in sanitized.unknown_properties
    )

    assert (
        "load-bearing capacity"
        in sanitized.unknown_properties
    )

    assert (
        "stacking stability"
        in sanitized.unknown_properties
    )

    caution_text = " ".join(
        sanitized.caution_notes
    ).lower()

    assert "contents" in caution_text
    assert (
        "load-bearing"
        in caution_text
        or "stability"
        in caution_text
    )
    assert "stack" in caution_text

    validate_object_dna(
        sanitized
    )

    print(
        "SANITIZER BOX UNCERTAINTY REPAIR TEST: passed"
    )


def main() -> None:
    test_electrical_requires_condition_unknown()

    test_container_requires_unknown_contents()

    test_container_requires_contents_caution()

    test_support_requires_load_unknown()

    test_support_requires_stability_or_load_caution()

    test_elevate_uses_same_load_guardrail()

    test_stack_requires_stackable_trait()

    test_stack_requires_stability_unknown()

    test_stack_requires_stability_caution()

    test_sanitizer_repairs_box_uncertainties()

    print()

    print(
        "OBJECT DNA HARDENING TEST: passed"
    )


if __name__ == "__main__":
    main()