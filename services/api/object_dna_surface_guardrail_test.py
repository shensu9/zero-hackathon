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


def make_surface_affordance() -> ObjectAffordance:
    return ObjectAffordance(
        capability=CapabilityType.PROVIDE_SURFACE,
        description="Provides a physical placement surface.",
        evidence_basis=EvidenceBasis.COMMON_PROPERTY,
        certainty=CertaintyLevel.HIGH,
    )


def test_sanitizer_removes_surface_without_flat_geometry() -> None:
    dna = ObjectDNA(
        item_id="stand_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
        ],
        affordances=[
            make_surface_affordance(),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    assert sanitized.affordances == []

    validate_object_dna(
        sanitized
    )

    print(
        "SURFACE WITHOUT FLAT GEOMETRY REMOVAL TEST: passed"
    )


def test_sanitizer_removes_flat_without_surface_size() -> None:
    dna = ObjectDNA(
        item_id="panel_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.FLAT
            ),
        ],
        affordances=[
            make_surface_affordance(),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    assert sanitized.affordances == []

    validate_object_dna(
        sanitized
    )

    print(
        "SURFACE WITHOUT SIZE TRAIT REMOVAL TEST: passed"
    )


def test_flat_large_surface_is_preserved() -> None:
    dna = ObjectDNA(
        item_id="desk_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.FLAT
            ),
            make_trait(
                PhysicalTraitType.LARGE_SURFACE
            ),
        ],
        affordances=[
            make_surface_affordance(),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    assert (
        len(sanitized.affordances)
        == 1
    )

    assert (
        sanitized.affordances[
            0
        ].capability
        == CapabilityType.PROVIDE_SURFACE
    )

    validate_object_dna(
        sanitized
    )

    print(
        "GROUNDED LARGE SURFACE PRESERVATION TEST: passed"
    )


def test_flat_small_surface_is_preserved() -> None:
    dna = ObjectDNA(
        item_id="tray_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.FLAT
            ),
            make_trait(
                PhysicalTraitType.SMALL_SURFACE
            ),
        ],
        affordances=[
            make_surface_affordance(),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    assert (
        len(sanitized.affordances)
        == 1
    )

    validate_object_dna(
        sanitized
    )

    print(
        "GROUNDED SMALL SURFACE PRESERVATION TEST: passed"
    )


def test_validator_rejects_surface_without_geometry() -> None:
    dna = ObjectDNA(
        item_id="bad_surface_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
        ],
        affordances=[
            make_surface_affordance(),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    try:
        validate_object_dna(
            dna
        )

    except ObjectDNAValidationError as exc:
        assert (
            "provide_surface requires flat plus "
            "large_surface or small_surface traits"
            in str(exc)
        )

        print(
            "SURFACE VALIDATOR REJECTION TEST: passed"
        )

        return

    raise AssertionError(
        "Validator accepted unsupported provide_surface."
    )


def main() -> None:
    test_sanitizer_removes_surface_without_flat_geometry()

    test_sanitizer_removes_flat_without_surface_size()

    test_flat_large_surface_is_preserved()

    test_flat_small_surface_is_preserved()

    test_validator_rejects_surface_without_geometry()

    print()

    print(
        "OBJECT DNA SURFACE GUARDRAIL TEST: passed"
    )


if __name__ == "__main__":
    main()