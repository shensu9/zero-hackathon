from walkthrough_entity_resolution_schemas import (
    WalkthroughEntityResolution,
)
from walkthrough_perception import (
    WalkthroughFrameObservation,
)


class EntityResolutionValidationError(
    ValueError
):
    pass


def _source_observation_ids(
    frames: list[
        WalkthroughFrameObservation
    ],
) -> list[str]:
    observation_ids = []

    for frame in frames:
        for observation in frame.objects:
            observation_ids.append(
                observation.observation_id
            )

    return observation_ids


def validate_entity_resolution(
    *,
    frames: list[
        WalkthroughFrameObservation
    ],
    resolution: WalkthroughEntityResolution,
) -> WalkthroughEntityResolution:
    """
    Enforce deterministic entity-resolution invariants.

    Semantic questions such as:

        "Are these two monitor sightings actually the same monitor?"

    remain the resolver model's responsibility.

    Structural guarantees are enforced here in code.
    """

    source_ids = (
        _source_observation_ids(
            frames
        )
    )

    # ------------------------------------------------------------------
    # SOURCE PERCEPTION ITSELF MUST BE WELL-FORMED
    # ------------------------------------------------------------------

    if (
        len(
            set(
                source_ids
            )
        )
        != len(
            source_ids
        )
    ):
        raise EntityResolutionValidationError(
            "Source walkthrough perception contains "
            "duplicate observation IDs."
        )

    source_set = set(
        source_ids
    )

    # ------------------------------------------------------------------
    # ENTITY ASSIGNMENTS
    # ------------------------------------------------------------------

    assigned_ids = []

    for entity_index, entity in enumerate(
        resolution.entities,
        start=1,
    ):
        entity_ids = (
            entity.observation_ids
        )

        if (
            len(
                set(
                    entity_ids
                )
            )
            != len(
                entity_ids
            )
        ):
            raise EntityResolutionValidationError(
                "Entity "
                f"{entity_index} "
                "contains duplicate observation IDs."
            )

        assigned_ids.extend(
            entity_ids
        )

    # One sighting cannot belong to two physical entities.
    if (
        len(
            set(
                assigned_ids
            )
        )
        != len(
            assigned_ids
        )
    ):
        duplicates = sorted(
            {
                observation_id
                for observation_id
                in assigned_ids
                if (
                    assigned_ids.count(
                        observation_id
                    )
                    > 1
                )
            }
        )

        raise EntityResolutionValidationError(
            "Observations were assigned to more "
            "than one physical entity: "
            f"{duplicates}"
        )

    assigned_set = set(
        assigned_ids
    )

    # ------------------------------------------------------------------
    # IGNORED OBSERVATIONS
    # ------------------------------------------------------------------

    ignored_ids = [
        ignored.observation_id
        for ignored
        in resolution.ignored_observations
    ]

    if (
        len(
            set(
                ignored_ids
            )
        )
        != len(
            ignored_ids
        )
    ):
        duplicates = sorted(
            {
                observation_id
                for observation_id
                in ignored_ids
                if (
                    ignored_ids.count(
                        observation_id
                    )
                    > 1
                )
            }
        )

        raise EntityResolutionValidationError(
            "Ignored observations contain "
            "duplicate IDs: "
            f"{duplicates}"
        )

    ignored_set = set(
        ignored_ids
    )

    # ------------------------------------------------------------------
    # NO INVENTED OBSERVATION IDS
    # ------------------------------------------------------------------

    output_ids = (
        assigned_set
        | ignored_set
    )

    unknown_ids = sorted(
        output_ids
        - source_set
    )

    if unknown_ids:
        raise EntityResolutionValidationError(
            "Entity resolution invented unknown "
            "observation IDs: "
            f"{unknown_ids}"
        )

    # ------------------------------------------------------------------
    # ONE OBSERVATION CANNOT BE BOTH RETAINED AND IGNORED
    # ------------------------------------------------------------------

    overlap = sorted(
        assigned_set
        & ignored_set
    )

    if overlap:
        raise EntityResolutionValidationError(
            "Observations cannot be both assigned "
            "to an entity and ignored: "
            f"{overlap}"
        )

    # ------------------------------------------------------------------
    # COMPLETE COVERAGE
    # ------------------------------------------------------------------

    missing_ids = sorted(
        source_set
        - output_ids
    )

    if missing_ids:
        raise EntityResolutionValidationError(
            "Entity resolution silently dropped "
            "source observations: "
            f"{missing_ids}"
        )

    # ------------------------------------------------------------------
    # EXACT ACCOUNTING
    # ------------------------------------------------------------------

    if (
        len(
            output_ids
        )
        != len(
            source_set
        )
    ):
        raise EntityResolutionValidationError(
            "Entity-resolution accounting mismatch."
        )

    return resolution