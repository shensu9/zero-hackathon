from walkthrough_entity_resolution_schemas import (
    IgnoredObservationReason,
)
from walkthrough_entity_resolver import (
    CompactEntityGroup,
    CompactEntityResolution,
    CompactIgnoredObservation,
    _hydrate_compact_resolution,
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
    confidence: float,
) -> WalkthroughObjectObservation:
    return WalkthroughObjectObservation(
        observation_id=observation_id,
        frame_sample_number=frame,
        name=name,
        description=description,
        location_hint=location_hint,
        confidence=confidence,
    )


def build_frames(
) -> list[
    WalkthroughFrameObservation
]:
    return [
        WalkthroughFrameObservation(
            sample_number=1,
            image_path="frame_01.jpg",
            objects=[
                observation(
                    observation_id="f01_o01",
                    frame=1,
                    name="computer monitor",
                    description=(
                        "black monitor on desk"
                    ),
                    location_hint="center",
                    confidence=0.95,
                ),
                observation(
                    observation_id="f01_o02",
                    frame=1,
                    name="blanket",
                    description=(
                        "beige plush blanket"
                    ),
                    location_hint="left",
                    confidence=0.97,
                ),
                observation(
                    observation_id="f01_o03",
                    frame=1,
                    name="blanket",
                    description=(
                        "gray plush blanket"
                    ),
                    location_hint="lower left",
                    confidence=0.96,
                ),
                observation(
                    observation_id="f01_o04",
                    frame=1,
                    name="door hinge",
                    description=(
                        "small metal door hinge"
                    ),
                    location_hint="right",
                    confidence=0.90,
                ),
            ],
        ),

        WalkthroughFrameObservation(
            sample_number=2,
            image_path="frame_02.jpg",
            objects=[
                observation(
                    observation_id="f02_o01",
                    frame=2,
                    name="computer monitor",
                    description=(
                        "black computer monitor "
                        "seen from another angle"
                    ),
                    location_hint="desk area",
                    confidence=0.98,
                ),
                observation(
                    observation_id="f02_o02",
                    frame=2,
                    name="books",
                    description=(
                        "small stack of books"
                    ),
                    location_hint="lower right",
                    confidence=0.85,
                ),
            ],
        ),
    ]


def main() -> None:
    frames = build_frames()

    compact = CompactEntityResolution(
        groups=[
            CompactEntityGroup(
                observation_ids=[
                    "f01_o01",
                    "f02_o01",
                ],
                merge_confidence=0.98,
            ),

            CompactEntityGroup(
                observation_ids=[
                    "f01_o02",
                ],
                merge_confidence=0.99,
            ),

            CompactEntityGroup(
                observation_ids=[
                    "f01_o03",
                ],
                merge_confidence=0.99,
            ),

            CompactEntityGroup(
                observation_ids=[
                    "f02_o02",
                ],
                merge_confidence=0.98,
            ),
        ],

        ignored=[
            CompactIgnoredObservation(
                observation_id=(
                    "f01_o04"
                ),
                reason=(
                    IgnoredObservationReason
                    .TINY_INCIDENTAL_DETAIL
                ),
            )
        ],
    )

    result = (
        _hydrate_compact_resolution(
            frames=frames,
            compact=compact,
        )
    )

    assert len(
        result.entities
    ) == 4

    assert len(
        result.ignored_observations
    ) == 1

    monitor = next(
        entity
        for entity
        in result.entities
        if set(
            entity.observation_ids
        )
        == {
            "f01_o01",
            "f02_o01",
        }
    )

    # Highest-confidence source sighting supplies
    # grounded metadata.
    assert (
        monitor.canonical_name
        == "computer monitor"
    )

    assert (
        monitor.canonical_description
        == (
            "black computer monitor "
            "seen from another angle"
        )
    )

    assert (
        monitor.location_hint
        == "desk area"
    )

    assert (
        monitor.merge_confidence
        == 0.98
    )

    ignored = (
        result
        .ignored_observations[
            0
        ]
    )

    assert (
        ignored.observation_id
        == "f01_o04"
    )

    assert (
        ignored.reason
        == (
            IgnoredObservationReason
            .TINY_INCIDENTAL_DETAIL
        )
    )

    # ---------------------------------------------------------------
    # COMPACT ACCOUNTING FAILURE
    # ---------------------------------------------------------------

    invalid = CompactEntityResolution(
        groups=[
            CompactEntityGroup(
                observation_ids=[
                    "f01_o01",
                    "f02_o01",
                ],
                merge_confidence=0.98,
            ),

            CompactEntityGroup(
                observation_ids=[
                    "f01_o02",
                ],
                merge_confidence=0.99,
            ),

            CompactEntityGroup(
                observation_ids=[
                    "f01_o03",
                ],
                merge_confidence=0.99,
            ),

            # f02_o02 intentionally omitted.
        ],

        ignored=[
            CompactIgnoredObservation(
                observation_id=(
                    "f01_o04"
                ),
                reason=(
                    IgnoredObservationReason
                    .TINY_INCIDENTAL_DETAIL
                ),
            )
        ],
    )

    try:
        _hydrate_compact_resolution(
            frames=frames,
            compact=invalid,
        )

    except RuntimeError as exc:
        assert (
            "silently dropped"
            in str(exc)
        )

        print(
            "MISSING COMPACT OBSERVATION: "
            "correctly rejected"
        )

    else:
        raise AssertionError(
            "Invalid compact resolution "
            "should have been rejected."
        )

    print(
        "COMPACT ENTITY RESOLVER TEST: passed"
    )


if __name__ == "__main__":
    main()