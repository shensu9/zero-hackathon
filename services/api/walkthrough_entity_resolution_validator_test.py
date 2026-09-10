from walkthrough_entity_resolution_schemas import (
    IgnoredObservationReason,
    IgnoredWalkthroughObservation,
    ResolvedPhysicalEntity,
    WalkthroughEntityResolution,
)
from walkthrough_entity_resolution_validator import (
    EntityResolutionValidationError,
    validate_entity_resolution,
)
from walkthrough_perception import (
    WalkthroughFrameObservation,
    WalkthroughObjectObservation,
)


def observation(
    *,
    observation_id: str,
    frame: int,
    name: str,
    description: str,
    location_hint: str,
    confidence: float = 0.9,
) -> WalkthroughObjectObservation:
    return WalkthroughObjectObservation(
        observation_id=(
            observation_id
        ),

        frame_sample_number=(
            frame
        ),

        name=name,

        description=(
            description
        ),

        location_hint=(
            location_hint
        ),

        confidence=(
            confidence
        ),
    )


def build_frames(
) -> list[
    WalkthroughFrameObservation
]:
    return [
        WalkthroughFrameObservation(
            sample_number=1,

            image_path=(
                "frame_01.jpg"
            ),

            objects=[
                observation(
                    observation_id="f01_o01",
                    frame=1,
                    name="computer monitor",
                    description=(
                        "black monitor on desk"
                    ),
                    location_hint=(
                        "center"
                    ),
                ),

                observation(
                    observation_id="f01_o02",
                    frame=1,
                    name="blanket",
                    description=(
                        "beige plush blanket"
                    ),
                    location_hint=(
                        "left"
                    ),
                ),

                observation(
                    observation_id="f01_o03",
                    frame=1,
                    name="blanket",
                    description=(
                        "gray plush blanket"
                    ),
                    location_hint=(
                        "lower left"
                    ),
                ),

                observation(
                    observation_id="f01_o04",
                    frame=1,
                    name="door hinge",
                    description=(
                        "small metal door hinge"
                    ),
                    location_hint=(
                        "far right"
                    ),
                ),
            ],
        ),

        WalkthroughFrameObservation(
            sample_number=2,

            image_path=(
                "frame_02.jpg"
            ),

            objects=[
                observation(
                    observation_id="f02_o01",
                    frame=2,
                    name="computer monitor",
                    description=(
                        "same black monitor "
                        "seen from another angle"
                    ),
                    location_hint=(
                        "left of desk"
                    ),
                ),

                observation(
                    observation_id="f02_o02",
                    frame=2,
                    name="books",
                    description=(
                        "small stack of books"
                    ),
                    location_hint=(
                        "lower right"
                    ),
                ),
            ],
        ),
    ]


def build_valid_resolution(
) -> WalkthroughEntityResolution:
    return WalkthroughEntityResolution(
        entities=[
            # Same physical monitor observed across two frames.
            ResolvedPhysicalEntity(
                canonical_name=(
                    "computer monitor"
                ),

                canonical_description=(
                    "black computer monitor "
                    "positioned at the desk"
                ),

                location_hint=(
                    "desk area"
                ),

                observation_ids=[
                    "f01_o01",
                    "f02_o01",
                ],

                merge_confidence=0.98,
            ),

            # Same object type does NOT mean same physical object.
            ResolvedPhysicalEntity(
                canonical_name=(
                    "beige blanket"
                ),

                canonical_description=(
                    "beige plush blanket"
                ),

                location_hint=(
                    "left side"
                ),

                observation_ids=[
                    "f01_o02",
                ],

                merge_confidence=0.99,
            ),

            ResolvedPhysicalEntity(
                canonical_name=(
                    "gray blanket"
                ),

                canonical_description=(
                    "gray plush blanket"
                ),

                location_hint=(
                    "lower left"
                ),

                observation_ids=[
                    "f01_o03",
                ],

                merge_confidence=0.99,
            ),

            ResolvedPhysicalEntity(
                canonical_name="books",

                canonical_description=(
                    "small stack of books"
                ),

                location_hint=(
                    "lower right"
                ),

                observation_ids=[
                    "f02_o02",
                ],

                merge_confidence=0.95,
            ),
        ],

        ignored_observations=[
            IgnoredWalkthroughObservation(
                observation_id=(
                    "f01_o04"
                ),

                reason=(
                    IgnoredObservationReason
                    .TINY_INCIDENTAL_DETAIL
                ),

                explanation=(
                    "Door hinge is incidental "
                    "built-in hardware."
                ),
            )
        ],
    )


def expect_failure(
    *,
    name: str,
    resolution: WalkthroughEntityResolution,
    expected_text: str,
) -> None:
    try:
        validate_entity_resolution(
            frames=build_frames(),
            resolution=resolution,
        )

    except EntityResolutionValidationError as exc:
        message = str(
            exc
        )

        assert (
            expected_text
            in message
        ), (
            f"{name}: expected error containing "
            f"{expected_text!r}, got {message!r}"
        )

        print(
            f"{name}: correctly rejected"
        )

    else:
        raise AssertionError(
            f"{name}: invalid resolution "
            "should have failed."
        )


def main() -> None:
    frames = build_frames()

    valid = build_valid_resolution()

    validated = (
        validate_entity_resolution(
            frames=frames,
            resolution=valid,
        )
    )

    assert (
        len(
            validated.entities
        )
        == 4
    )

    print(
        "VALID ENTITY RESOLUTION: passed"
    )

    # ------------------------------------------------------------------
    # UNKNOWN / INVENTED OBSERVATION ID
    # ------------------------------------------------------------------

    invented = build_valid_resolution()

    invented.entities[
        0
    ].observation_ids.append(
        "f99_o99"
    )

    expect_failure(
        name=(
            "INVENTED OBSERVATION"
        ),

        resolution=invented,

        expected_text=(
            "invented unknown observation IDs"
        ),
    )

    # ------------------------------------------------------------------
    # ONE SIGHTING ASSIGNED TO TWO ENTITIES
    # ------------------------------------------------------------------

    duplicate_assignment = (
        build_valid_resolution()
    )

    duplicate_assignment.entities[
        1
    ].observation_ids.append(
        "f01_o01"
    )

    expect_failure(
        name=(
            "DUPLICATE ENTITY ASSIGNMENT"
        ),

        resolution=(
            duplicate_assignment
        ),

        expected_text=(
            "more than one physical entity"
        ),
    )

    # ------------------------------------------------------------------
    # RETAINED + IGNORED SIMULTANEOUSLY
    # ------------------------------------------------------------------

    overlap = build_valid_resolution()

    overlap.ignored_observations.append(
        IgnoredWalkthroughObservation(
            observation_id=(
                "f02_o02"
            ),

            reason=(
                IgnoredObservationReason
                .OTHER
            ),

            explanation=(
                "Deliberately invalid overlap."
            ),
        )
    )

    expect_failure(
        name=(
            "ASSIGNED AND IGNORED"
        ),

        resolution=overlap,

        expected_text=(
            "both assigned to an entity "
            "and ignored"
        ),
    )

    # ------------------------------------------------------------------
    # SILENTLY DROPPED SOURCE OBSERVATION
    # ------------------------------------------------------------------

    missing = build_valid_resolution()

    missing.entities = [
        entity
        for entity
        in missing.entities
        if (
            "f02_o02"
            not in entity.observation_ids
        )
    ]

    expect_failure(
        name=(
            "SILENTLY DROPPED OBSERVATION"
        ),

        resolution=missing,

        expected_text=(
            "silently dropped source observations"
        ),
    )

    print()
    print(
        "ENTITY RESOLUTION VALIDATOR TEST: passed"
    )


if __name__ == "__main__":
    main()