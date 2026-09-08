from schemas import (
    CapabilityType,
    ObjectDNA,
    PhysicalTraitType,
)


class ObjectDNAValidationError(ValueError):
    pass


def trait_names(dna: ObjectDNA) -> set[PhysicalTraitType]:
    return {
        trait.trait
        for trait in dna.physical_traits
    }


def capability_names(dna: ObjectDNA) -> set[CapabilityType]:
    return {
        affordance.capability
        for affordance in dna.affordances
    }


def validate_object_dna(dna: ObjectDNA) -> ObjectDNA:
    traits = trait_names(dna)
    capabilities = capability_names(dna)

    errors: list[str] = []

    # ------------------------------------------------------------------
    # Electrical guardrails
    # ------------------------------------------------------------------

    if CapabilityType.PROVIDE_POWER_CONNECTION in capabilities:
        required = {
            PhysicalTraitType.ELECTRICAL,
            PhysicalTraitType.HAS_ELECTRICAL_OUTLETS,
        }

        if not required.issubset(traits):
            errors.append(
                "provide_power_connection requires both "
                "electrical and has_electrical_outlets traits."
            )

    if PhysicalTraitType.ELECTRICAL in traits:
        unknown_text = " ".join(
            dna.unknown_properties
        ).lower()

        if "rating" not in unknown_text:
            errors.append(
                "Electrical objects must preserve unknown electrical rating."
            )

        if not dna.caution_notes:
            errors.append(
                "Electrical objects must include at least one safety caution."
            )

    # ------------------------------------------------------------------
    # Liquid-container guardrails
    # ------------------------------------------------------------------

    if CapabilityType.DISPENSE_LIQUID in capabilities:
        required = {
            PhysicalTraitType.HAS_NOZZLE,
            PhysicalTraitType.CAN_DISPENSE_LIQUID,
        }

        if not required.issubset(traits):
            errors.append(
                "dispense_liquid requires has_nozzle and "
                "can_dispense_liquid traits."
            )

    if CapabilityType.CONTAIN in capabilities:
        if (
            PhysicalTraitType.HOLLOW not in traits
            and PhysicalTraitType.CAN_HOLD_LIQUID not in traits
        ):
            errors.append(
                "contain requires hollow or can_hold_liquid."
            )

    if PhysicalTraitType.CAN_HOLD_LIQUID in traits:
        unknown_text = " ".join(
            dna.unknown_properties
        ).lower()

        if (
            "content" not in unknown_text
            and "liquid" not in unknown_text
        ):
            errors.append(
                "Liquid containers must preserve unknown contents."
            )

    # ------------------------------------------------------------------
    # Reuse-quality guardrails
    # ------------------------------------------------------------------

    if (
        CapabilityType.PROVIDE_WEIGHT in capabilities
        and PhysicalTraitType.WEIGHTED not in traits
    ):
        errors.append(
            "provide_weight requires a grounded weighted trait."
        )

    if (
        CapabilityType.BLOCK_LIGHT in capabilities
        and (
            PhysicalTraitType.OPAQUE not in traits
            or PhysicalTraitType.LARGE_SURFACE not in traits
        )
    ):
        errors.append(
            "block_light requires opaque and large_surface traits."
        )

    if (
        CapabilityType.DAMPEN_SOUND in capabilities
        or CapabilityType.ABSORB_SOUND in capabilities
    ):
        if (
            PhysicalTraitType.SOFT not in traits
            and PhysicalTraitType.FLEXIBLE not in traits
        ):
            errors.append(
                "Sound-dampening capabilities require a "
                "soft or flexible material trait."
            )

    if errors:
        raise ObjectDNAValidationError(
            f"{dna.item_id}: " + " | ".join(errors)
        )

    return dna