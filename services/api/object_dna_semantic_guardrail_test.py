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
        evidence_basis=(
            EvidenceBasis.COMMON_PROPERTY
        ),
        certainty=(
            CertaintyLevel.HIGH
        ),
        note=(
            f"Test trait: {trait.value}."
        ),
    )


def make_affordance(
    capability: CapabilityType,
    description: str,
    *,
    evidence_basis: EvidenceBasis = (
        EvidenceBasis.COMMON_PROPERTY
    ),
) -> ObjectAffordance:
    return ObjectAffordance(
        capability=capability,
        description=description,
        evidence_basis=(
            evidence_basis
        ),
        certainty=(
            CertaintyLevel.MEDIUM
        ),
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
        if (
            expected_text
            not in str(exc)
        ):
            raise AssertionError(
                "Validator failed, but not for the "
                "expected reason.\n"
                f"Expected: {expected_text}\n"
                f"Actual: {exc}"
            )

        return

    raise AssertionError(
        "Expected ObjectDNAValidationError "
        "was not raised."
    )


def test_removes_destructive_hang_claim():
    dna = ObjectDNA(
        item_id="door_frame",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.HANG,
                (
                    "Provides a place to hang "
                    "objects using nails or adhesives."
                ),
            ),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    assert (
        CapabilityType.HANG
        not in {
            affordance.capability
            for affordance
            in sanitized.affordances
        }
    )

    validate_object_dna(
        sanitized
    )

    print(
        "DESTRUCTIVE HANG REMOVAL TEST: passed"
    )


def test_validator_rejects_destructive_hang():
    dna = ObjectDNA(
        item_id="door_frame",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.HANG,
                "Hang objects with screws.",
            ),
        ],
        unknown_properties=[
            "attachment method",
        ],
        caution_notes=[],
    )

    expect_validation_error(
        dna,
        "hang capability must not depend",
    )

    print(
        "DESTRUCTIVE HANG VALIDATOR TEST: passed"
    )


def test_handle_hang_is_preserved():
    dna = ObjectDNA(
        item_id="bag",
        physical_traits=[
            make_trait(
                PhysicalTraitType.FLEXIBLE
            ),
            make_trait(
                PhysicalTraitType.PORTABLE
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.HANG,
                (
                    "Handles allow the bag "
                    "to be suspended from a hook."
                ),
                evidence_basis=(
                    EvidenceBasis.VISUALLY_OBSERVED
                ),
            ),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    assert (
        len(
            sanitized.affordances
        )
        == 1
    )

    assert (
        sanitized.affordances[
            0
        ].capability
        == CapabilityType.HANG
    )

    assert (
        "attachment method"
        not in {
            value.lower()
            for value
            in sanitized.unknown_properties
        }
    )

    validate_object_dna(
        sanitized
    )

    print(
        "HANDLE HANG PRESERVATION TEST: passed"
    )


def test_blanket_preserves_fit_uncertainty():
    dna = ObjectDNA(
        item_id="blanket",
        physical_traits=[
            make_trait(
                PhysicalTraitType.FLEXIBLE
            ),
            make_trait(
                PhysicalTraitType.FLAT
            ),
            make_trait(
                PhysicalTraitType.SOFT
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.COVER,
                "Can be draped over another object.",
            ),
            make_affordance(
                CapabilityType.HANG,
                (
                    "Can be hung from a line "
                    "for drying or storage."
                ),
            ),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    unknowns = {
        value.lower()
        for value
        in sanitized.unknown_properties
    }

    assert (
        "dimensions"
        in unknowns
    )

    assert (
        "coverage area"
        in unknowns
    )

    assert (
        "attachment method"
        in unknowns
    )

    validate_object_dna(
        sanitized
    )

    print(
        "BLANKET FIT UNCERTAINTY TEST: passed"
    )


def test_column_elevate_is_removed():
    dna = ObjectDNA(
        item_id="column",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
            make_trait(
                PhysicalTraitType.WEIGHTED
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.SUPPORT,
                "Can bear structural loads.",
                evidence_basis=(
                    EvidenceBasis.VISUALLY_OBSERVED
                ),
            ),
            make_affordance(
                CapabilityType.ELEVATE,
                (
                    "Can raise objects to a "
                    "higher vertical position."
                ),
                evidence_basis=(
                    EvidenceBasis.VISUALLY_OBSERVED
                ),
            ),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    capabilities = {
        affordance.capability
        for affordance
        in sanitized.affordances
    }

    assert (
        CapabilityType.SUPPORT
        in capabilities
    )

    assert (
        CapabilityType.ELEVATE
        not in capabilities
    )

    support = next(
        affordance
        for affordance
        in sanitized.affordances
        if (
            affordance.capability
            == CapabilityType.SUPPORT
        )
    )

    assert (
        support.evidence_basis
        == EvidenceBasis.COMMON_PROPERTY
    )

    assert (
        "load-bearing capacity"
        in sanitized.unknown_properties
    )

    validate_object_dna(
        sanitized
    )

    print(
        "COLUMN ELEVATE REMOVAL TEST: passed"
    )


def test_flat_shelf_elevate_is_preserved():
    dna = ObjectDNA(
        item_id="shelf",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
            make_trait(
                PhysicalTraitType.FLAT
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.SUPPORT,
                "Can hold objects on its surface.",
                evidence_basis=(
                    EvidenceBasis.VISUALLY_OBSERVED
                ),
            ),
            make_affordance(
                CapabilityType.ELEVATE,
                (
                    "Holds objects above "
                    "the floor level."
                ),
                evidence_basis=(
                    EvidenceBasis.VISUALLY_OBSERVED
                ),
            ),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    capabilities = {
        affordance.capability
        for affordance
        in sanitized.affordances
    }

    assert (
        CapabilityType.SUPPORT
        in capabilities
    )

    assert (
        CapabilityType.ELEVATE
        in capabilities
    )

    for affordance in (
        sanitized.affordances
    ):
        if (
            affordance.capability
            in {
                CapabilityType.SUPPORT,
                CapabilityType.ELEVATE,
            }
        ):
            assert (
                affordance.evidence_basis
                == EvidenceBasis.COMMON_PROPERTY
            )

    validate_object_dna(
        sanitized
    )

    print(
        "FLAT SHELF ELEVATE PRESERVATION TEST: passed"
    )


def test_validator_rejects_elevate_without_geometry():
    dna = ObjectDNA(
        item_id="column",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.SUPPORT,
                "Can support another object.",
            ),
            make_affordance(
                CapabilityType.ELEVATE,
                "Can elevate another object.",
            ),
        ],
        unknown_properties=[
            "load-bearing capacity",
        ],
        caution_notes=[
            (
                "Verify stability and "
                "load-bearing capacity before reuse."
            ),
        ],
    )

    expect_validation_error(
        dna,
        "elevate requires grounded placement",
    )

    print(
        "ELEVATE GEOMETRY VALIDATOR TEST: passed"
    )


def test_validator_rejects_cover_without_size_unknowns():
    dna = ObjectDNA(
        item_id="blanket",
        physical_traits=[
            make_trait(
                PhysicalTraitType.FLEXIBLE
            ),
            make_trait(
                PhysicalTraitType.FLAT
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.COVER,
                "Can cover another object.",
            ),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    expect_validation_error(
        dna,
        "unknown dimensions",
    )

    print(
        "COVER DIMENSION VALIDATOR TEST: passed"
    )


def test_trash_can_weight_is_removed():
    dna = ObjectDNA(
        item_id="trash_can",
        physical_traits=[
            make_trait(
                PhysicalTraitType.WEIGHTED
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.PROVIDE_WEIGHT,
                (
                    "Its mass can be used to hold down "
                    "lightweight objects."
                ),
            ),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    assert (
        CapabilityType.PROVIDE_WEIGHT
        not in {
            affordance.capability
            for affordance
            in sanitized.affordances
        }
    )

    validate_object_dna(
        sanitized
    )

    print(
        "TRASH CAN WEIGHT REMOVAL TEST: passed"
    )


def test_portable_weight_is_preserved():
    dna = ObjectDNA(
        item_id="paperweight",
        physical_traits=[
            make_trait(
                PhysicalTraitType.WEIGHTED
            ),
            make_trait(
                PhysicalTraitType.PORTABLE
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.PROVIDE_WEIGHT,
                (
                    "Portable weighted object "
                    "can hold papers down."
                ),
            ),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    assert (
        CapabilityType.PROVIDE_WEIGHT
        in {
            affordance.capability
            for affordance
            in sanitized.affordances
        }
    )

    validate_object_dna(
        sanitized
    )

    print(
        "PORTABLE WEIGHT PRESERVATION TEST: passed"
    )


def test_fixed_floor_block_light_is_removed():
    dna = ObjectDNA(
        item_id="wood_flooring",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
            make_trait(
                PhysicalTraitType.FLAT
            ),
            make_trait(
                PhysicalTraitType.LARGE_SURFACE
            ),
            make_trait(
                PhysicalTraitType.OPAQUE
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.BLOCK_LIGHT,
                (
                    "As an opaque panel, it can "
                    "obstruct light transmission."
                ),
            ),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    assert (
        CapabilityType.BLOCK_LIGHT
        not in {
            affordance.capability
            for affordance
            in sanitized.affordances
        }
    )

    validate_object_dna(
        sanitized
    )

    print(
        "FIXED FLOOR BLOCK-LIGHT REMOVAL TEST: passed"
    )


def test_repositionable_light_blocker_is_preserved():
    dna = ObjectDNA(
        item_id="curtain_material",
        physical_traits=[
            make_trait(
                PhysicalTraitType.FLEXIBLE
            ),
            make_trait(
                PhysicalTraitType.FLAT
            ),
            make_trait(
                PhysicalTraitType.LARGE_SURFACE
            ),
            make_trait(
                PhysicalTraitType.OPAQUE
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.BLOCK_LIGHT,
                (
                    "Opaque flexible material can "
                    "block light when positioned "
                    "across an opening."
                ),
            ),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    capabilities = {
        affordance.capability
        for affordance
        in sanitized.affordances
    }

    assert (
        CapabilityType.BLOCK_LIGHT
        in capabilities
    )

    unknowns = {
        value.lower()
        for value
        in sanitized.unknown_properties
    }

    assert (
        "dimensions"
        in unknowns
    )

    assert (
        "coverage area"
        in unknowns
    )

    validate_object_dna(
        sanitized
    )

    print(
        "REPOSITIONABLE BLOCK-LIGHT PRESERVATION TEST: passed"
    )


def test_unknown_property_semantic_dedup():
    dna = ObjectDNA(
        item_id="water_bottle",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
            make_trait(
                PhysicalTraitType.HOLLOW
            ),
            make_trait(
                PhysicalTraitType.CAN_HOLD_LIQUID
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.CONTAIN,
                "Can hold liquid inside its interior.",
            ),
        ],
        unknown_properties=[
            "current_liquid_contents",
            "insulation_effectiveness",
        ],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    semantic_unknowns = [
        " ".join(
            value
            .lower()
            .replace("_", " ")
            .split()
        )
        for value
        in sanitized.unknown_properties
    ]

    assert (
        semantic_unknowns.count(
            "current liquid contents"
        )
        == 1
    )

    assert (
        "current liquid contents"
        in semantic_unknowns
    )

    assert (
        "insulation effectiveness"
        in semantic_unknowns
    )

    validate_object_dna(
        sanitized
    )

    print(
        "UNKNOWN PROPERTY SEMANTIC DEDUP TEST: passed"
    )


def main() -> None:
    tests = [
        test_removes_destructive_hang_claim,
        test_validator_rejects_destructive_hang,
        test_handle_hang_is_preserved,
        test_blanket_preserves_fit_uncertainty,
        test_column_elevate_is_removed,
        test_flat_shelf_elevate_is_preserved,
        test_validator_rejects_elevate_without_geometry,
        test_validator_rejects_cover_without_size_unknowns,
        test_trash_can_weight_is_removed,
        test_portable_weight_is_preserved,
        test_fixed_floor_block_light_is_removed,
        test_repositionable_light_blocker_is_preserved,
        test_unknown_property_semantic_dedup,
    ]

    for test in tests:
        test()

    print()

    print(
        f"{len(tests)}/{len(tests)} "
        "Object DNA semantic guardrail tests passed"
    )

    print(
        "Model calls: 0"
    )


if __name__ == "__main__":
    main()
