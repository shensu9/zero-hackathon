from schemas import (
    CapabilityType,
    ObjectDNA,
    PhysicalTraitType,
)


def _trait_names(
    dna: ObjectDNA,
) -> set[PhysicalTraitType]:
    return {
        trait.trait
        for trait in dna.physical_traits
    }


def _capability_names(
    dna: ObjectDNA,
) -> set[CapabilityType]:
    return {
        affordance.capability
        for affordance in dna.affordances
    }


def _prioritize_strings(
    required: list[str],
    existing: list[str],
    maximum: int,
) -> list[str]:
    """
    Put required safety facts first, remove duplicates,
    and stay inside the schema's maximum list length.
    """

    result: list[str] = []

    for value in required + existing:
        normalized = value.strip()

        if not normalized:
            continue

        if normalized.lower() in {
            item.lower()
            for item in result
        }:
            continue

        result.append(normalized)

        if len(result) >= maximum:
            break

    return result


def sanitize_object_dna(
    dna: ObjectDNA,
) -> ObjectDNA:
    """
    Apply deterministic ZERO guardrails.

    This function is allowed to:

    - remove affordances whose required physical evidence is missing
    - preserve mandatory unknown physical properties
    - preserve mandatory safety cautions

    It does NOT invent new creative affordances.
    """

    traits = _trait_names(
        dna
    )

    cleaned_affordances = []

    for affordance in dna.affordances:
        capability = affordance.capability

        # ---------------------------------------------------------------
        # Electrical
        # ---------------------------------------------------------------

        if (
            capability
            == CapabilityType.PROVIDE_POWER_CONNECTION
        ):
            required = {
                PhysicalTraitType.ELECTRICAL,
                PhysicalTraitType.HAS_ELECTRICAL_OUTLETS,
            }

            if not required.issubset(
                traits
            ):
                continue

        # ---------------------------------------------------------------
        # Liquid / container handling
        # ---------------------------------------------------------------

        if (
            capability
            == CapabilityType.DISPENSE_LIQUID
        ):
            required = {
                PhysicalTraitType.HAS_NOZZLE,
                PhysicalTraitType.CAN_DISPENSE_LIQUID,
            }

            if not required.issubset(
                traits
            ):
                continue

        if (
            capability
            == CapabilityType.CONTAIN
        ):
            if (
                PhysicalTraitType.HOLLOW
                not in traits
                and PhysicalTraitType.CAN_HOLD_LIQUID
                not in traits
            ):
                continue

        # ---------------------------------------------------------------
        # Physical reuse
        # ---------------------------------------------------------------

        if (
            capability
            == CapabilityType.PROVIDE_WEIGHT
        ):
            if (
                PhysicalTraitType.WEIGHTED
                not in traits
            ):
                continue

        if (
            capability
            == CapabilityType.STACK
        ):
            if (
                PhysicalTraitType.STACKABLE
                not in traits
            ):
                continue

        if (
            capability
            == CapabilityType.BLOCK_LIGHT
        ):
            required = {
                PhysicalTraitType.OPAQUE,
                PhysicalTraitType.LARGE_SURFACE,
            }

            if not required.issubset(
                traits
            ):
                continue

        if capability in {
            CapabilityType.ABSORB_SOUND,
            CapabilityType.DAMPEN_SOUND,
        }:
            if (
                PhysicalTraitType.SOFT
                not in traits
                and PhysicalTraitType.FLEXIBLE
                not in traits
            ):
                continue

        cleaned_affordances.append(
            affordance
        )

    cleaned_dna = dna.model_copy(
        update={
            "affordances": cleaned_affordances,
        }
    )

    capabilities = _capability_names(
        cleaned_dna
    )

    # -------------------------------------------------------------------
    # Required unknown physical properties
    # -------------------------------------------------------------------

    required_unknowns: list[str] = []

    if (
        PhysicalTraitType.ELECTRICAL
        in traits
    ):
        required_unknowns.append(
            "electrical rating"
        )

        required_unknowns.append(
            "electrical condition"
        )

    if (
        PhysicalTraitType.CAN_HOLD_LIQUID
        in traits
    ):
        required_unknowns.append(
            "current liquid contents"
        )

    elif (
        CapabilityType.CONTAIN
        in capabilities
    ):
        required_unknowns.append(
            "current contents"
        )

    if (
        CapabilityType.SUPPORT
        in capabilities
        or CapabilityType.ELEVATE
        in capabilities
    ):
        required_unknowns.append(
            "load-bearing capacity"
        )

    if (
        CapabilityType.STACK
        in capabilities
    ):
        required_unknowns.append(
            "stacking stability"
        )

    unknown_properties = _prioritize_strings(
        required=required_unknowns,
        existing=dna.unknown_properties,
        maximum=4,
    )

    # -------------------------------------------------------------------
    # Required safety cautions
    # -------------------------------------------------------------------

    required_cautions: list[str] = []

    if (
        PhysicalTraitType.ELECTRICAL
        in traits
    ):
        required_cautions.append(
            "Verify electrical rating and condition before reuse."
        )

    if (
        PhysicalTraitType.CAN_HOLD_LIQUID
        in traits
    ):
        required_cautions.append(
            "Identify the current liquid contents before reuse."
        )

    elif (
        CapabilityType.CONTAIN
        in capabilities
    ):
        required_cautions.append(
            "Check current contents before repurposing the container."
        )

    if (
        CapabilityType.SUPPORT
        in capabilities
        or CapabilityType.ELEVATE
        in capabilities
    ):
        required_cautions.append(
            "Verify stability and load-bearing capacity before supporting or elevating objects."
        )

    if (
        CapabilityType.STACK
        in capabilities
    ):
        required_cautions.append(
            "Verify stacking stability before reuse."
        )

    caution_notes = _prioritize_strings(
        required=required_cautions,
        existing=dna.caution_notes,
        maximum=3,
    )

    return cleaned_dna.model_copy(
        update={
            "unknown_properties": (
                unknown_properties
            ),
            "caution_notes": (
                caution_notes
            ),
        }
    )