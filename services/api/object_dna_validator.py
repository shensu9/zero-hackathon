from schemas import (
    CapabilityType,
    ObjectDNA,
    PhysicalTraitType,
)


class ObjectDNAValidationError(ValueError):
    pass


def trait_names(
    dna: ObjectDNA,
) -> set[PhysicalTraitType]:
    return {
        trait.trait
        for trait in dna.physical_traits
    }


def capability_names(
    dna: ObjectDNA,
) -> set[CapabilityType]:
    return {
        affordance.capability
        for affordance in dna.affordances
    }


def _combined_text(
    values: list[str],
) -> str:
    return " ".join(
        values
    ).lower()


def validate_object_dna(
    dna: ObjectDNA,
) -> ObjectDNA:
    traits = trait_names(
        dna
    )

    capabilities = capability_names(
        dna
    )

    unknown_text = _combined_text(
        dna.unknown_properties
    )

    caution_text = _combined_text(
        dna.caution_notes
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
        if "rating" not in unknown_text:
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
                "Electrical objects must include at least one "
                "safety caution."
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
            and PhysicalTraitType.CAN_HOLD_LIQUID
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
            and "repurpos"
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
            and "liquid"
            not in unknown_text
        ):
            errors.append(
                "Liquid containers must preserve unknown contents."
            )

    # ------------------------------------------------------------------
    # Support / elevation guardrails
    # ------------------------------------------------------------------

    if (
        CapabilityType.SUPPORT
        in capabilities
        or CapabilityType.ELEVATE
        in capabilities
    ):
        if (
            "load"
            not in unknown_text
            and "weight"
            not in unknown_text
            and "capacity"
            not in unknown_text
        ):
            errors.append(
                "support/elevate capabilities must preserve unknown "
                "load-bearing capacity."
            )

        if (
            "stability"
            not in caution_text
            and "load"
            not in caution_text
        ):
            errors.append(
                "support/elevate capabilities must include a "
                "stability/load caution."
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
            and "stability"
            not in unknown_text
        ):
            errors.append(
                "stack capability must preserve unknown "
                "stacking stability."
            )

        if (
            "stack"
            not in caution_text
            and "stability"
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
                or PhysicalTraitType.SMALL_SURFACE
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
        and PhysicalTraitType.WEIGHTED
        not in traits
    ):
        errors.append(
            "provide_weight requires a grounded weighted trait."
        )

    if (
        CapabilityType.BLOCK_LIGHT
        in capabilities
        and (
            PhysicalTraitType.OPAQUE
            not in traits
            or PhysicalTraitType.LARGE_SURFACE
            not in traits
        )
    ):
        errors.append(
            "block_light requires opaque and large_surface traits."
        )

    if (
        CapabilityType.DAMPEN_SOUND
        in capabilities
        or CapabilityType.ABSORB_SOUND
        in capabilities
    ):
        if (
            PhysicalTraitType.SOFT
            not in traits
            and PhysicalTraitType.FLEXIBLE
            not in traits
        ):
            errors.append(
                "Sound-dampening capabilities require a "
                "soft or flexible material trait."
            )

    if errors:
        raise ObjectDNAValidationError(
            f"{dna.item_id}: "
            + " | ".join(errors)
        )

    return dna