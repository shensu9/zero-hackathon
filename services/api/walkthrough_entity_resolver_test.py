from walkthrough_entity_resolver import (
    SameObjectLink,
    WindowEntityLinks,
    _build_components,
    _frame_windows,
    _hydrate_components,
    _validate_link_proposals,
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
    confidence: float = 0.95,
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


def empty_frame(
    number: int,
) -> WalkthroughFrameObservation:
    return WalkthroughFrameObservation(
        sample_number=number,
        image_path=(
            f"frame_{number:02d}.jpg"
        ),
        objects=[],
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
                    location_hint="desk",
                    confidence=0.95,
                ),

                observation(
                    observation_id="f01_o02",
                    frame=1,
                    name="blanket",
                    description=(
                        "beige plush blanket"
                    ),
                    location_hint="bed",
                    confidence=0.97,
                ),

                observation(
                    observation_id="f01_o03",
                    frame=1,
                    name="blanket",
                    description=(
                        "gray plush blanket"
                    ),
                    location_hint="bed",
                    confidence=0.96,
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
                        "same black monitor from "
                        "another desk angle"
                    ),
                    location_hint="desk",
                    confidence=0.98,
                ),

                observation(
                    observation_id="f02_o02",
                    frame=2,
                    name="blanket",
                    description=(
                        "plush blanket partly visible"
                    ),
                    location_hint="bed",
                    confidence=0.80,
                ),
            ],
        ),

        WalkthroughFrameObservation(
            sample_number=3,
            image_path="frame_03.jpg",
            objects=[
                observation(
                    observation_id="f03_o01",
                    frame=3,
                    name="computer monitor",
                    description=(
                        "black monitor at workstation"
                    ),
                    location_hint="desk",
                    confidence=0.96,
                ),
            ],
        ),
    ]


def main() -> None:
    # ------------------------------------------------------------------
    # WINDOW SHAPE
    # ------------------------------------------------------------------

    windows = _frame_windows(
        [
            empty_frame(
                number
            )
            for number
            in range(
                1,
                9,
            )
        ]
    )

    assert [
        [
            frame.sample_number
            for frame
            in window
        ]
        for window
        in windows
    ] == [
        [
            1,
            2,
            3,
            4,
        ],
        [
            3,
            4,
            5,
            6,
        ],
        [
            5,
            6,
            7,
            8,
        ],
    ]

    print(
        "FRAME WINDOWS TEST: passed"
    )

    # ------------------------------------------------------------------
    # MODEL PROPOSALS
    # ------------------------------------------------------------------

    frames = build_frames()

    proposals = (
        WindowEntityLinks(
            links=[
                # Valid monitor chain.
                SameObjectLink(
                    a="f01_o01",
                    b="f02_o01",
                    confidence=0.98,
                ),

                SameObjectLink(
                    a="f02_o01",
                    b="f03_o01",
                    confidence=0.97,
                ),

                # The ambiguous frame-2 blanket may correspond to
                # either of two frame-1 blankets. Both are proposed
                # deliberately so union protection can resolve the
                # same-frame conflict.
                SameObjectLink(
                    a="f01_o02",
                    b="f02_o02",
                    confidence=0.96,
                ),

                SameObjectLink(
                    a="f01_o03",
                    b="f02_o02",
                    confidence=0.95,
                ),

                # Invalid: same-frame merge.
                SameObjectLink(
                    a="f01_o02",
                    b="f01_o03",
                    confidence=0.99,
                ),

                # Invalid: below confidence threshold.
                SameObjectLink(
                    a="f01_o03",
                    b="f03_o01",
                    confidence=0.50,
                ),
            ]
        )
    )

    valid_links, rejected = (
        _validate_link_proposals(
            window_frames=frames,
            proposals=proposals,
        )
    )

    assert rejected == 2

    assert len(
        valid_links
    ) == 4

    print(
        "INVALID LINK PROPOSALS: safely discarded"
    )

    # ------------------------------------------------------------------
    # UNION / SAME-FRAME CONFLICT PROTECTION
    # ------------------------------------------------------------------

    (
        components,
        accepted_links,
        conflict_rejections,
    ) = _build_components(
        frames=frames,
        links=valid_links,
    )

    # Stronger beige-blanket link wins.
    # The later gray-blanket link would create two frame-1 sightings
    # inside the same component and must therefore be rejected.
    assert (
        conflict_rejections
        == 1
    )

    monitor_component = next(
        component
        for component
        in components
        if "f01_o01"
        in component
    )

    assert set(
        monitor_component
    ) == {
        "f01_o01",
        "f02_o01",
        "f03_o01",
    }

    beige_component = next(
        component
        for component
        in components
        if "f01_o02"
        in component
    )

    assert set(
        beige_component
    ) == {
        "f01_o02",
        "f02_o02",
    }

    gray_component = next(
        component
        for component
        in components
        if "f01_o03"
        in component
    )

    assert gray_component == [
        "f01_o03"
    ]

    print(
        "SAME-FRAME TRANSITIVE CONFLICT: "
        "safely rejected"
    )

    # ------------------------------------------------------------------
    # FULL HYDRATION / EXACT ACCOUNTING
    # ------------------------------------------------------------------

    resolution = (
        _hydrate_components(
            frames=frames,
            components=components,
            accepted_links=(
                accepted_links
            ),
        )
    )

    assert len(
        resolution.entities
    ) == 3

    assert (
        resolution
        .ignored_observations
        == []
    )

    accounted = sum(
        len(
            entity.observation_ids
        )
        for entity
        in resolution.entities
    )

    assert accounted == 6

    monitor = next(
        entity
        for entity
        in resolution.entities
        if set(
            entity.observation_ids
        )
        == {
            "f01_o01",
            "f02_o01",
            "f03_o01",
        }
    )

    # Weakest accepted link in the identity chain controls
    # component merge confidence.
    assert (
        monitor.merge_confidence
        == 0.97
    )

    print(
        "CHUNKED ENTITY RESOLVER TEST: passed"
    )


if __name__ == "__main__":
    main()