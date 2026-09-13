from __future__ import annotations

from schemas import (
    CapabilityType,
    EvidenceBasis,
    ObjectDNA,
    PhysicalTraitType,
)


# External methods that should not be converted into an intrinsic
# HANG affordance for the object being analyzed.
#
# ZERO may later choose an available fastening object during planning,
# but Object DNA must not pretend the analyzed object itself already
# provides that capability.
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


def _trait_names(
    dna: ObjectDNA,
) -> set[PhysicalTraitType]:
    return {
        trait.trait
        for trait
        in dna.physical_traits
    }


def _capability_names(
    dna: ObjectDNA,
) -> set[CapabilityType]:
    return {
        affordance.capability
        for affordance
        in dna.affordances
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

    for value in (
        required
        + existing
    ):
        normalized = (
            value.strip()
        )

        if not normalized:
            continue

        if normalized.lower() in {
            item.lower()
            for item
            in result
        }:
            continue

        result.append(
            normalized
        )

        if (
            len(result)
            >= maximum
        ):
            break

    return result


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


def _hang_depends_on_added_attachment(
    description: str,
) -> bool:
    """
    Return True when a HANG claim depends on introducing
    nails, screws, drilling, adhesive, tape, etc.

    Those methods may be considered separately during planning
    if such resources actually exist, but they are not an
    intrinsic affordance of the analyzed object.
    """

    return _contains_any(
        description,
        DESTRUCTIVE_OR_ADDED_ATTACHMENT_TERMS,
    )


def _hang_has_intrinsic_mechanism(
    description: str,
) -> bool:
    """
    Identify descriptions that establish a built-in or
    body-geometry hanging mechanism.

    This is deliberately conservative.
    """

    return _contains_any(
        description,
        INTRINSIC_HANG_MECHANISM_TERMS,
    )


def _downgrade_structural_evidence(
    affordance,
):
    """
    SUPPORT/ELEVATE are easy for a model to over-label as
    visually observed.

    Without the source image at this deterministic boundary,
    downgrade these functional claims to common_property.

    This never creates a new affordance and never raises
    certainty.
    """

    if (
        affordance.capability
        not in {
            CapabilityType.SUPPORT,
            CapabilityType.ELEVATE,
        }
    ):
        return affordance

    if (
        affordance.evidence_basis
        != EvidenceBasis.VISUALLY_OBSERVED
    ):
        return affordance

    return affordance.model_copy(
        update={
            "evidence_basis":
                EvidenceBasis.COMMON_PROPERTY,
        },
        deep=True,
    )


def sanitize_object_dna(
    dna: ObjectDNA,
) -> ObjectDNA:
    """
    Apply deterministic ZERO guardrails.

    This function is allowed to:

    - remove affordances whose required physical evidence is missing
    - remove affordances that depend on ungrounded external modification
    - conservatively downgrade overly strong evidence labels
    - preserve mandatory unknown physical properties
    - preserve mandatory safety cautions

    It does NOT invent new creative affordances.
    """

    traits = _trait_names(
        dna
    )

    # -------------------------------------------------------------------
    # First-pass affordance filtering
    # -------------------------------------------------------------------

    first_pass_affordances = []

    for raw_affordance in (
        dna.affordances
    ):
        affordance = (
            _downgrade_structural_evidence(
                raw_affordance
            )
        )

        capability = (
            affordance.capability
        )

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
                and
                PhysicalTraitType.CAN_HOLD_LIQUID
                not in traits
            ):
                continue

        # ---------------------------------------------------------------
        # Hanging
        # ---------------------------------------------------------------

        if (
            capability
            == CapabilityType.HANG
        ):
            if (
                _hang_depends_on_added_attachment(
                    affordance.description
                )
            ):
                continue

        # ---------------------------------------------------------------
        # Physical reuse
        # ---------------------------------------------------------------

        if (
            capability
            == CapabilityType.PROVIDE_SURFACE
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
                continue

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

        if (
            capability
            in {
                CapabilityType.ABSORB_SOUND,
                CapabilityType.DAMPEN_SOUND,
            }
        ):
            if (
                PhysicalTraitType.SOFT
                not in traits
                and
                PhysicalTraitType.FLEXIBLE
                not in traits
            ):
                continue

        first_pass_affordances.append(
            affordance
        )

    # -------------------------------------------------------------------
    # Elevation semantics
    # -------------------------------------------------------------------

    first_pass_capabilities = {
        affordance.capability
        for affordance
        in first_pass_affordances
    }

    cleaned_affordances = []

    for affordance in (
        first_pass_affordances
    ):
        if (
            affordance.capability
            != CapabilityType.ELEVATE
        ):
            cleaned_affordances.append(
                affordance
            )

            continue

        # Elevating something necessarily implies supporting it.
        if (
            CapabilityType.SUPPORT
            not in first_pass_capabilities
        ):
            continue

        # Being tall, fixed, or structural is not enough.
        #
        # Require either:
        # - flat placement geometry, or
        # - a valid hanging/suspension capability.
        has_elevation_geometry = (
            PhysicalTraitType.FLAT
            in traits
            or
            CapabilityType.HANG
            in first_pass_capabilities
        )

        if not has_elevation_geometry:
            continue

        cleaned_affordances.append(
            affordance
        )

    cleaned_dna = (
        dna.model_copy(
            update={
                "affordances":
                    cleaned_affordances,
            },
            deep=True,
        )
    )

    capabilities = (
        _capability_names(
            cleaned_dna
        )
    )

    # -------------------------------------------------------------------
    # Required unknown physical properties
    # -------------------------------------------------------------------

    required_unknowns: list[
        str
    ] = []

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
        or
        CapabilityType.ELEVATE
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

    # Flexible, sheet-like cover materials must not silently
    # imply that they are large enough for a later target.
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
        required_unknowns.append(
            "dimensions"
        )

        required_unknowns.append(
            "coverage area"
        )

    # If an object can hang but no intrinsic hanging feature is
    # established in the affordance description, preserve the
    # method as unknown rather than silently assuming hardware.
    hang_affordances = [
        affordance
        for affordance
        in cleaned_dna.affordances
        if (
            affordance.capability
            == CapabilityType.HANG
        )
    ]

    if hang_affordances:
        intrinsic_hang_established = any(
            _hang_has_intrinsic_mechanism(
                affordance.description
            )
            for affordance
            in hang_affordances
        )

        if not intrinsic_hang_established:
            required_unknowns.append(
                "attachment method"
            )

    unknown_properties = (
        _prioritize_strings(
            required=(
                required_unknowns
            ),
            existing=(
                dna.unknown_properties
            ),
            maximum=4,
        )
    )

    # -------------------------------------------------------------------
    # Required safety cautions
    # -------------------------------------------------------------------

    required_cautions: list[
        str
    ] = []

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
        or
        CapabilityType.ELEVATE
        in capabilities
    ):
        required_cautions.append(
            "Verify stability and load-bearing capacity before "
            "supporting or elevating objects."
        )

    if (
        CapabilityType.STACK
        in capabilities
    ):
        required_cautions.append(
            "Verify stacking stability before reuse."
        )

    if (
        hang_affordances
        and "attachment method"
        in {
            value.lower()
            for value
            in unknown_properties
        }
    ):
        required_cautions.append(
            "Verify a stable, non-damaging attachment method "
            "before hanging."
        )

    caution_notes = (
        _prioritize_strings(
            required=(
                required_cautions
            ),
            existing=(
                dna.caution_notes
            ),
            maximum=3,
        )
    )

    return cleaned_dna.model_copy(
        update={
            "unknown_properties":
                unknown_properties,
            "caution_notes":
                caution_notes,
        },
        deep=True,
    )