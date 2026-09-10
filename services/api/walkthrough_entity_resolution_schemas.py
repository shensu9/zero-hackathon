from enum import Enum

from pydantic import BaseModel, Field


class IgnoredObservationReason(
    str,
    Enum,
):
    INTEGRATED_COMPONENT = (
        "integrated_component"
    )

    TINY_INCIDENTAL_DETAIL = (
        "tiny_incidental_detail"
    )

    NON_INDEPENDENT_PART = (
        "non_independent_part"
    )

    LOW_CONFIDENCE_OR_AMBIGUOUS = (
        "low_confidence_or_ambiguous"
    )

    OTHER = "other"


class ResolvedPhysicalEntity(
    BaseModel,
):
    """
    A candidate real-world physical object reconstructed from one
    or more walkthrough observations.

    This is still pre-CanonicalInventory.

    Stable inventory IDs are generated in the next layer rather than
    trusted to the model.
    """

    canonical_name: str = Field(
        min_length=1,
        max_length=120,
    )

    canonical_description: str = Field(
        min_length=1,
        max_length=500,
    )

    location_hint: str = Field(
        min_length=1,
        max_length=300,
    )

    observation_ids: list[str] = Field(
        min_length=1,
        max_length=20,
    )

    merge_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    identity_uncertainty: (
        str
        | None
    ) = Field(
        default=None,
        max_length=300,
    )


class IgnoredWalkthroughObservation(
    BaseModel,
):
    observation_id: str = Field(
        min_length=1,
    )

    reason: IgnoredObservationReason

    explanation: str = Field(
        min_length=1,
        max_length=300,
    )


class WalkthroughEntityResolution(
    BaseModel,
):
    """
    Cross-frame entity-resolution result.

    Every source observation must appear exactly once:

        entity.observation_ids

    OR

        ignored_observations

    Never both.
    Never neither.
    """

    entities: list[
        ResolvedPhysicalEntity
    ] = Field(
        default_factory=list,
        max_length=100,
    )

    ignored_observations: list[
        IgnoredWalkthroughObservation
    ] = Field(
        default_factory=list,
        max_length=100,
    )