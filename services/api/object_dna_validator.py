from __future__ import annotations

from schemas import (
    CapabilityType,
    EvidenceBasis,
    ObjectDNA,
    PhysicalTraitType,
)


class ObjectDNAValidationError(
    ValueError
):
    pass


DESTRUCTIVE_OR_ADDED_ATTACHMENT_TERMS = (
    "nail",
    "nails",
    "screw",
    "screws",
    "drill",
    "drilling",
    "adhesive",
    "adhesives",
    "tape",
    "glue",
    "wall anchor",
    "wall anchors",
    "staple",
    "staples",
)


INTRINSIC_HANG_MECHANISM_TERMS = (
    "handle",
    "handles",
    "loop",
    "loops",
    "strap",
    "straps",
    "eyelet",
    "eyelets",
    "grommet",
    "grommets",
    "clip",
    "clips",
    "clamp",
    "clamps",
    "rod pocket",
    "built-in hook",
    "built in hook",
    "drape over",
    "draped over",
)


def trait_names(
    dna: ObjectDNA,
) -> set[PhysicalTraitType]:
    return {
        trait.trait
        for trait
        in dna.physical_traits
    }


def capability_names(
    dna: ObjectDNA,
) -> set[CapabilityType]:
    return {
        affordance.capability
        for affordance
        in dna.affordances
    }


def _combined_text(
    values: list[str],
) -> str:
    return " ".join(
        values
    ).lower()


def _contains_any(
    text: str,
    terms: tuple[str, ...],
) -> bool:
    lowered = text.lower()

    return any(
        term in lowered
        for term
        in terms
    )


def _hang_has_intrinsic_mechanism(
    description: str,
) -> bool:
    return _contains_any(
        description,
        INTRINSIC_HANG_MECHANISM_TERMS,
    )


def validate_object_dna(
    dna: ObjectDNA,
) -> ObjectDNA:
    traits = trait_names(
        dna
    )

    capabilities = capability_names(
        dna
    )

    unknown_text = (
        _combined_text(
            dna.unknown_properties
        )
    )

    caution_text = (
        _combined_text(
            dna.caution_notes
        )
    )

    errors: list[str] = []

    # ------------------------------------------------------------------
    # Electrical guardrails
    # ------------------------------------------------------------------

    if (
        CapabilityType.PROVIDE_POWER_CONNECTION
        in capabilities
    ):
        required = {
            PhysicalTraitType.ELECTRICAL,
            PhysicalTraitType.HAS_ELECTRICAL_OUTLETS,
        }

        if not required.issubset(
            traits
        ):
            errors.append(
                "provide_power_connection requires both "
                "electrical and has_electrical_outlets traits."
            )

    if (
        PhysicalTraitType.ELECTRICAL
        in traits
    ):
        if (
            "rating"
            not in unknown_text
        ):
            errors.append(
                "Electrical objects must preserve unknown "
                "electrical rating."
            )

        if (
            "condition"
            not in unknown_text
        ):
            errors.append(
                "Electrical objects must preserve unknown "
                "electrical condition."
            )

        if not dna.caution_notes:
            errors.append(
                "Electrical objects must include at least "
                "one safety caution."
            )

    # ------------------------------------------------------------------
    # Liquid / container guardrails
    # ------------------------------------------------------------------

    if (
        CapabilityType.DISPENSE_LIQUID
        in capabilities
    ):
        required = {
            PhysicalTraitType.HAS_NOZZLE,
            PhysicalTraitType.CAN_DISPENSE_LIQUID,
        }

        if not required.issubset(
            traits
        ):
            errors.append(
                "dispense_liquid requires has_nozzle and "
                "can_dispense_liquid traits."
            )

    if (
        CapabilityType.CONTAIN
        in capabilities
    ):
        if (
            PhysicalTraitType.HOLLOW
            not in traits
            and
            PhysicalTraitType.CAN_HOLD_LIQUID
            not in traits
        ):
            errors.append(
                "contain requires hollow or can_hold_liquid."
            )

        if (
            "content"
            not in unknown_text
        ):
            errors.append(
                "Containers must preserve unknown current contents."
            )

        if (
            "content"
            not in caution_text
            and
            "repurpos"
            not in caution_text
        ):
            errors.append(
                "Containers must include a caution to inspect "
                "current contents before reuse."
            )

    if (
        PhysicalTraitType.CAN_HOLD_LIQUID
        in traits
    ):
        if (
            "content"
            not in unknown_text
            and
            "liquid"
            not in unknown_text
        ):
            errors.append(
                "Liquid containers must preserve unknown contents."
            )

    # ------------------------------------------------------------------
    # Hanging guardrails
    # ------------------------------------------------------------------

    hang_affordances = [
        affordance
        for affordance
        in dna.affordances
        if (
            affordance.capability
            == CapabilityType.HANG
        )
    ]

    for affordance in (
        hang_affordances
    ):
        if (
            _contains_any(
                affordance.description,
                DESTRUCTIVE_OR_ADDED_ATTACHMENT_TERMS,
            )
        ):
            errors.append(
                "hang capability must not depend on added nails, "
                "screws, drilling, adhesive, tape, glue, anchors, "
                "or staples."
            )

    if hang_affordances:
        intrinsic_hang_established = any(
            _hang_has_intrinsic_mechanism(
                affordance.description
            )
            for affordance
            in hang_affordances
        )

        if (
            not intrinsic_hang_established
            and
            "attachment"
            not in unknown_text
        ):
            errors.append(
                "hang capability without an intrinsic hanging "
                "mechanism must preserve unknown attachment method."
            )

    # ------------------------------------------------------------------
    # Support / elevation guardrails
    # ------------------------------------------------------------------

    structural_affordances = [
        affordance
        for affordance
        in dna.affordances
        if (
            affordance.capability
            in {
                CapabilityType.SUPPORT,
                CapabilityType.ELEVATE,
            }
        )
    ]

    for affordance in (
        structural_affordances
    ):
        if (
            affordance.evidence_basis
            == EvidenceBasis.VISUALLY_OBSERVED
        ):
            errors.append(
                "support/elevate functional claims must not use "
                "visually_observed evidence at the Object DNA "
                "boundary; use conservative common_property or "
                "uncertain evidence."
            )

    if (
        CapabilityType.SUPPORT
        in capabilities
        or
        CapabilityType.ELEVATE
        in capabilities
    ):
        if (
            "load"
            not in unknown_text
            and
            "weight"
            not in unknown_text
            and
            "capacity"
            not in unknown_text
        ):
            errors.append(
                "support/elevate capabilities must preserve "
                "unknown load-bearing capacity."
            )

        if (
            "stability"
            not in caution_text
            and
            "load"
            not in caution_text
        ):
            errors.append(
                "support/elevate capabilities must include a "
                "stability/load caution."
            )

    if (
        CapabilityType.ELEVATE
        in capabilities
    ):
        if (
            CapabilityType.SUPPORT
            not in capabilities
        ):
            errors.append(
                "elevate requires a grounded support capability."
            )

        has_elevation_geometry = (
            PhysicalTraitType.FLAT
            in traits
            or
            CapabilityType.HANG
            in capabilities
        )

        if not has_elevation_geometry:
            errors.append(
                "elevate requires grounded placement or suspension "
                "geometry: flat or hang."
            )

    # ------------------------------------------------------------------
    # Stack guardrails
    # ------------------------------------------------------------------

    if (
        CapabilityType.STACK
        in capabilities
    ):
        if (
            PhysicalTraitType.STACKABLE
            not in traits
        ):
            errors.append(
                "stack requires a grounded stackable trait."
            )

        if (
            "stack"
            not in unknown_text
            and
            "stability"
            not in unknown_text
        ):
            errors.append(
                "stack capability must preserve unknown "
                "stacking stability."
            )

        if (
            "stack"
            not in caution_text
            and
            "stability"
            not in caution_text
        ):
            errors.append(
                "stack capability must include a stacking "
                "stability caution."
            )

    # ------------------------------------------------------------------
    # Reuse-quality guardrails
    # ------------------------------------------------------------------

    if (
        CapabilityType.PROVIDE_SURFACE
        in capabilities
    ):
        has_surface_geometry = (
            PhysicalTraitType.FLAT
            in traits
            and (
                PhysicalTraitType.LARGE_SURFACE
                in traits
                or
                PhysicalTraitType.SMALL_SURFACE
                in traits
            )
        )

        if not has_surface_geometry:
            errors.append(
                "provide_surface requires flat plus "
                "large_surface or small_surface traits."
            )

    if (
        CapabilityType.PROVIDE_WEIGHT
        in capabilities
    ):
        if (
            PhysicalTraitType.WEIGHTED
            not in traits
        ):
            errors.append(
                "provide_weight requires a grounded weighted trait."
            )

        if (
            PhysicalTraitType.PORTABLE
            not in traits
        ):
            errors.append(
                "provide_weight requires a portable weighted object."
            )

    if (
        CapabilityType.BLOCK_LIGHT
        in capabilities
        and (
            PhysicalTraitType.OPAQUE
            not in traits
            or
            PhysicalTraitType.LARGE_SURFACE
            not in traits
        )
    ):
        errors.append(
            "block_light requires opaque and large_surface traits."
        )

    if (
        CapabilityType.DAMPEN_SOUND
        in capabilities
        or
        CapabilityType.ABSORB_SOUND
        in capabilities
    ):
        if (
            PhysicalTraitType.SOFT
            not in traits
            and
            PhysicalTraitType.FLEXIBLE
            not in traits
        ):
            errors.append(
                "Sound-dampening capabilities require a "
                "soft or flexible material trait."
            )

    # ------------------------------------------------------------------
    # Flexible cover / target-fit uncertainty
    # ------------------------------------------------------------------

    if (
        PhysicalTraitType.FLEXIBLE
        in traits
        and
        PhysicalTraitType.FLAT
        in traits
        and (
            CapabilityType.COVER
            in capabilities
            or
            CapabilityType.BLOCK_LIGHT
            in capabilities
        )
    ):
        if (
            "dimension"
            not in unknown_text
            and
            "size"
            not in unknown_text
        ):
            errors.append(
                "flexible flat cover materials must preserve "
                "unknown dimensions."
            )

        if (
            "coverage"
            not in unknown_text
            and
            "area"
            not in unknown_text
        ):
            errors.append(
                "flexible flat cover materials must preserve "
                "unknown coverage area."
            )

    if errors:
        raise ObjectDNAValidationError(
            f"{dna.item_id}: "
            + " | ".join(
                errors
            )
        )

    return dna
