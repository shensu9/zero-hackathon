from copy import deepcopy

from object_dna_normalizer import (
    normalize_object_dna_payload,
)
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
        note=f"Grounded test trait: {trait.value}.",
    )


def make_affordance(
    capability: CapabilityType,
) -> ObjectAffordance:
    return ObjectAffordance(
        capability=capability,
        description=f"Grounded test capability: {capability.value}.",
        evidence_basis=EvidenceBasis.COMMON_PROPERTY,
        certainty=CertaintyLevel.HIGH,
    )


def test_normalizer_repairs_known_aliases_without_mutating_input() -> None:
    payload = {
        "item_id": "test_item",
        "physical_traits": [
            {
                "property": "electrical",
                "evidence": "common_property",
                "certainty": "high",
                "description": "Ordinary electrical object.",
            }
        ],
        "affordances": [
            {
                "trait": "provide_power_connection",
                "note": "Can provide an electrical connection.",
                "evidence": "common_property",
                "certainty": "high",
            }
        ],
        "unknown_properties": [],
        "caution_notes": [],
    }

    original = deepcopy(payload)

    normalized = normalize_object_dna_payload(
        payload
    )

    assert payload == original

    trait = normalized[
        "physical_traits"
    ][0]

    assert trait["trait"] == "electrical"
    assert (
        trait["evidence_basis"]
        == "common_property"
    )
    assert (
        trait["note"]
        == "Ordinary electrical object."
    )

    affordance = normalized[
        "affordances"
    ][0]

    assert (
        affordance["capability"]
        == "provide_power_connection"
    )

    assert (
        affordance["description"]
        == "Can provide an electrical connection."
    )

    assert (
        affordance["evidence_basis"]
        == "common_property"
    )

    print(
        "OBJECT DNA NORMALIZER ALIAS TEST: passed"
    )


def test_electrical_pipeline_preserves_grounded_power_connection() -> None:
    raw_payload = {
        "item_id": "power_strip_01",
        "physical_traits": [
            {
                "property": "electrical",
                "evidence": "common_property",
                "certainty": "high",
                "description": "Electrical device.",
            },
            {
                "property": "has_electrical_outlets",
                "evidence": "visually_observed",
                "certainty": "high",
                "description": "Visible receptacles are present.",
            },
        ],
        "affordances": [
            {
                "property": "provide_power_connection",
                "reason": (
                    "Provides genuine electrical receptacles."
                ),
                "evidence": "common_property",
                "certainty": "high",
            }
        ],
        "unknown_properties": [],
        "caution_notes": [],
    }

    normalized = normalize_object_dna_payload(
        raw_payload
    )

    dna = ObjectDNA.model_validate(
        normalized
    )

    sanitized = sanitize_object_dna(
        dna
    )

    validated = validate_object_dna(
        sanitized
    )

    capabilities = {
        affordance.capability
        for affordance in validated.affordances
    }

    assert (
        CapabilityType.PROVIDE_POWER_CONNECTION
        in capabilities
    )

    assert (
        validated.unknown_properties[
            0
        ]
        == "electrical rating"
    )

    assert (
        validated.unknown_properties[
            1
        ]
        == "electrical condition"
    )

    assert (
        validated.caution_notes[
            0
        ]
        == (
            "Verify electrical rating and condition "
            "before reuse."
        )
    )

    print(
        "GROUNDED ELECTRICAL PIPELINE TEST: passed"
    )


def test_sanitizer_removes_ungrounded_power_connection() -> None:
    dna = ObjectDNA(
        item_id="electrical_item_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.ELECTRICAL
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.PROVIDE_POWER_CONNECTION
            ),
        ],
        unknown_properties=[],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    assert sanitized.affordances == []

    assert (
        "electrical rating"
        in sanitized.unknown_properties
    )

    assert (
        "electrical condition"
        in sanitized.unknown_properties
    )

    validate_object_dna(
        sanitized
    )

    print(
        "UNGROUNDED POWER AFFORDANCE REMOVAL TEST: passed"
    )


def test_sanitizer_removes_invalid_contain_affordance() -> None:
    dna = ObjectDNA(
        item_id="flat_object_01",
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
                CapabilityType.CONTAIN
            ),
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
        "INVALID CONTAIN AFFORDANCE REMOVAL TEST: passed"
    )


def test_liquid_container_safety_facts_are_preserved() -> None:
    dna = ObjectDNA(
        item_id="bottle_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.HOLLOW
            ),
            make_trait(
                PhysicalTraitType.CAN_HOLD_LIQUID
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.CONTAIN
            ),
        ],
        unknown_properties=[
            "exact capacity",
        ],
        caution_notes=[],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    validated = validate_object_dna(
        sanitized
    )

    capabilities = {
        affordance.capability
        for affordance in validated.affordances
    }

    assert (
        CapabilityType.CONTAIN
        in capabilities
    )

    assert (
        validated.unknown_properties[
            0
        ]
        == "current liquid contents"
    )

    assert (
        validated.caution_notes[
            0
        ]
        == (
            "Identify the current liquid contents "
            "before reuse."
        )
    )

    print(
        "LIQUID CONTAINER SAFETY TEST: passed"
    )


def test_safety_unknowns_take_priority_inside_schema_limit() -> None:
    dna = ObjectDNA(
        item_id="electrical_item_02",
        physical_traits=[
            make_trait(
                PhysicalTraitType.ELECTRICAL
            ),
            make_trait(
                PhysicalTraitType.HAS_ELECTRICAL_OUTLETS
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.PROVIDE_POWER_CONNECTION
            ),
        ],
        unknown_properties=[
            "existing unknown one",
            "existing unknown two",
            "existing unknown three",
            "existing unknown four",
        ],
        caution_notes=[
            "Existing caution one.",
            "Existing caution two.",
            "Existing caution three.",
        ],
    )

    sanitized = sanitize_object_dna(
        dna
    )

    assert len(
        sanitized.unknown_properties
    ) == 4

    assert (
        sanitized.unknown_properties[
            :2
        ]
        == [
            "electrical rating",
            "electrical condition",
        ]
    )

    assert len(
        sanitized.caution_notes
    ) == 3

    assert (
        sanitized.caution_notes[
            0
        ]
        == (
            "Verify electrical rating and condition "
            "before reuse."
        )
    )

    validate_object_dna(
        sanitized
    )

    print(
        "SAFETY PRIORITY WITHIN SCHEMA LIMIT TEST: passed"
    )


def test_validator_rejects_unsupported_power_connection() -> None:
    dna = ObjectDNA(
        item_id="bad_power_item_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.ELECTRICAL
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.PROVIDE_POWER_CONNECTION
            ),
        ],
        unknown_properties=[
            "electrical rating",
        ],
        caution_notes=[
            (
                "Verify electrical rating and condition "
                "before reuse."
            ),
        ],
    )

    try:
        validate_object_dna(
            dna
        )

    except ObjectDNAValidationError as exc:
        assert (
            "provide_power_connection requires both "
            "electrical and has_electrical_outlets traits"
            in str(exc)
        )

        print(
            "OBJECT DNA VALIDATOR REJECTION TEST: passed"
        )

        return

    raise AssertionError(
        "Validator accepted an unsupported "
        "provide_power_connection capability."
    )


def test_sanitizer_removes_unsupported_block_light() -> None:
    dna = ObjectDNA(
        item_id="small_opaque_item_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.OPAQUE
            ),
            make_trait(
                PhysicalTraitType.SMALL_SURFACE
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.BLOCK_LIGHT
            ),
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
        "UNGROUNDED BLOCK-LIGHT REMOVAL TEST: passed"
    )


def test_sanitizer_removes_unsupported_sound_dampening() -> None:
    dna = ObjectDNA(
        item_id="rigid_item_01",
        physical_traits=[
            make_trait(
                PhysicalTraitType.RIGID
            ),
        ],
        affordances=[
            make_affordance(
                CapabilityType.DAMPEN_SOUND
            ),
            make_affordance(
                CapabilityType.ABSORB_SOUND
            ),
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
        "UNGROUNDED SOUND AFFORDANCE REMOVAL TEST: passed"
    )


def main() -> None:
    test_normalizer_repairs_known_aliases_without_mutating_input()

    test_electrical_pipeline_preserves_grounded_power_connection()

    test_sanitizer_removes_ungrounded_power_connection()

    test_sanitizer_removes_invalid_contain_affordance()

    test_liquid_container_safety_facts_are_preserved()

    test_safety_unknowns_take_priority_inside_schema_limit()

    test_validator_rejects_unsupported_power_connection()

    test_sanitizer_removes_unsupported_block_light()

    test_sanitizer_removes_unsupported_sound_dampening()

    print()

    print(
        "OBJECT DNA DETERMINISTIC PIPELINE TEST: passed"
    )


if __name__ == "__main__":
    main()