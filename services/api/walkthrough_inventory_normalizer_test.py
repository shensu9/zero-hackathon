from schemas import (
    VerificationStatus,
)
from walkthrough_entity_resolution_schemas import (
    ResolvedPhysicalEntity,
    WalkthroughEntityResolution,
)
from walkthrough_inventory_normalizer import (
    ExcludedEntityReason,
    normalize_walkthrough_inventory,
)


def entity(
    *,
    name: str,
    description: str,
    location: str,
    observation_ids: list[str],
    confidence: float,
    uncertainty: str | None = None,
) -> ResolvedPhysicalEntity:
    return ResolvedPhysicalEntity(
        canonical_name=name,

        canonical_description=(
            description
        ),

        location_hint=(
            location
        ),

        observation_ids=(
            observation_ids
        ),

        merge_confidence=(
            confidence
        ),

        identity_uncertainty=(
            uncertainty
        ),
    )


def main() -> None:
    resolution = (
        WalkthroughEntityResolution(
            entities=[
                # ------------------------------------------------------
                # Strong repeated object.
                # ------------------------------------------------------

                entity(
                    name=(
                        "computer monitor"
                    ),

                    description=(
                        "black monitor on desk"
                    ),

                    location=(
                        "desk area"
                    ),

                    observation_ids=[
                        "f01_o01",
                        "f02_o01",
                    ],

                    confidence=0.98,
                ),

                # ------------------------------------------------------
                # Two distinct blankets visible simultaneously.
                #
                # Same-frame evidence means they must NOT be flagged
                # as duplicate multiplicity risk.
                # ------------------------------------------------------

                entity(
                    name="blanket",

                    description=(
                        "beige plush blanket"
                    ),

                    location="bed",

                    observation_ids=[
                        "f01_o02"
                    ],

                    confidence=0.96,
                ),

                entity(
                    name="blanket",

                    description=(
                        "gray plush blanket"
                    ),

                    location="bed",

                    observation_ids=[
                        "f01_o03"
                    ],

                    confidence=0.95,
                ),

                # ------------------------------------------------------
                # Potential false split:
                #
                # nightstand and side table appear in different frames.
                #
                # Both are otherwise high-confidence and could reach
                # planning, so multiplicity must be protected.
                # ------------------------------------------------------

                entity(
                    name="nightstand",

                    description=(
                        "small white bedside table"
                    ),

                    location=(
                        "beside bed"
                    ),

                    observation_ids=[
                        "f03_o01"
                    ],

                    confidence=0.95,
                ),

                entity(
                    name=(
                        "small white side table"
                    ),

                    description=(
                        "square white table/nightstand"
                    ),

                    location=(
                        "beneath keyboard"
                    ),

                    observation_ids=[
                        "f04_o01"
                    ],

                    confidence=0.95,
                ),

                # ------------------------------------------------------
                # Low-confidence real object.
                # ------------------------------------------------------

                entity(
                    name=(
                        "small black object"
                    ),

                    description=(
                        "small black accessory"
                    ),

                    location=(
                        "keyboard"
                    ),

                    observation_ids=[
                        "f04_o02"
                    ],

                    confidence=0.50,
                ),

                # ------------------------------------------------------
                # Same generic name across different frames, but BOTH
                # are already low-confidence.
                #
                # They should remain NEEDS_CONFIRMATION because of
                # confidence, but they should NOT create an additional
                # active-resource duplicate group.
                # ------------------------------------------------------

                entity(
                    name="small box",

                    description=(
                        "small box on desk"
                    ),

                    location="desk",

                    observation_ids=[
                        "f05_o10"
                    ],

                    confidence=0.70,
                ),

                entity(
                    name="small box",

                    description=(
                        "small box near wardrobe"
                    ),

                    location="wardrobe",

                    observation_ids=[
                        "f07_o10"
                    ],

                    confidence=0.70,
                ),

                # ------------------------------------------------------
                # Tiny non-independent hardware.
                # ------------------------------------------------------

                entity(
                    name="door hinge",

                    description=(
                        "metal hinge attached to door"
                    ),

                    location=(
                        "door edge"
                    ),

                    observation_ids=[
                        "f01_o04"
                    ],

                    confidence=0.95,
                ),

                # ------------------------------------------------------
                # Complete parent.
                # ------------------------------------------------------

                entity(
                    name="wardrobe",

                    description=(
                        "white built-in wardrobe"
                    ),

                    location=(
                        "center"
                    ),

                    observation_ids=[
                        "f07_o01"
                    ],

                    confidence=0.98,
                ),

                # ------------------------------------------------------
                # Explicit same-frame integrated component.
                # ------------------------------------------------------

                entity(
                    name="drawers",

                    description=(
                        "white drawers integrated "
                        "into the wardrobe"
                    ),

                    location=(
                        "center"
                    ),

                    observation_ids=[
                        "f07_o02"
                    ],

                    confidence=0.95,
                ),
            ],

            ignored_observations=[],
        )
    )

    result = (
        normalize_walkthrough_inventory(
            resolution
        )
    )

    items_by_name = {}

    for item in (
        result.inventory.items
    ):
        items_by_name.setdefault(
            item.name,
            [],
        ).append(
            item
        )

    # ------------------------------------------------------------------
    # EXPLICIT FILTERING
    # ------------------------------------------------------------------

    excluded_names = {
        excluded.name
        for excluded
        in result.excluded_entities
    }

    assert (
        "door hinge"
        in excluded_names
    )

    assert (
        "drawers"
        in excluded_names
    )

    assert (
        len(
            result.excluded_entities
        )
        == 2
    )

    hinge = next(
        excluded
        for excluded
        in result.excluded_entities
        if (
            excluded.name
            == "door hinge"
        )
    )

    assert (
        hinge.reason
        == (
            ExcludedEntityReason
            .TINY_INCIDENTAL_DETAIL
        )
    )

    drawers = next(
        excluded
        for excluded
        in result.excluded_entities
        if (
            excluded.name
            == "drawers"
        )
    )

    assert (
        drawers.reason
        == (
            ExcludedEntityReason
            .INTEGRATED_COMPONENT
        )
    )

    print(
        "NON-INDEPENDENT FILTER TEST: passed"
    )

    # ------------------------------------------------------------------
    # STRONG ACCEPTED ITEM
    # ------------------------------------------------------------------

    monitor = (
        items_by_name[
            "computer monitor"
        ][
            0
        ]
    )

    assert (
        monitor.verification_status
        == (
            VerificationStatus
            .AUTO_ACCEPTED
        )
    )

    assert (
        monitor.id
        == "computer_monitor_f01_o01"
    )

    print(
        "STABLE ID + AUTO ACCEPT TEST: passed"
    )

    # ------------------------------------------------------------------
    # SAME-FRAME MULTIPLICITY
    # ------------------------------------------------------------------

    blankets = (
        items_by_name[
            "blanket"
        ]
    )

    assert len(
        blankets
    ) == 2

    assert all(
        item.verification_status
        == (
            VerificationStatus
            .AUTO_ACCEPTED
        )
        for item
        in blankets
    )

    blanket_ids = {
        item.id
        for item
        in blankets
    }

    assert not any(
        blanket_ids
        .intersection(
            group.item_ids
        )
        for group
        in result.potential_duplicate_groups
    )

    print(
        "SAME-FRAME DISTINCT OBJECT TEST: passed"
    )

    # ------------------------------------------------------------------
    # FALSE-SPLIT PROTECTION
    # ------------------------------------------------------------------

    nightstand = (
        items_by_name[
            "nightstand"
        ][
            0
        ]
    )

    side_table = (
        items_by_name[
            "small white side table"
        ][
            0
        ]
    )

    assert (
        nightstand.verification_status
        == (
            VerificationStatus
            .NEEDS_CONFIRMATION
        )
    )

    assert (
        side_table.verification_status
        == (
            VerificationStatus
            .NEEDS_CONFIRMATION
        )
    )

    duplicate_group = next(
        group
        for group
        in result.potential_duplicate_groups
        if {
            nightstand.id,
            side_table.id,
        }.issubset(
            set(
                group.item_ids
            )
        )
    )

    assert (
        len(
            duplicate_group.item_ids
        )
        == 2
    )

    print(
        "FALSE-SPLIT PROTECTION TEST: passed"
    )

    # ------------------------------------------------------------------
    # ALREADY-PENDING DUPLICATE SUPPRESSION
    # ------------------------------------------------------------------

    small_boxes = (
        items_by_name[
            "small box"
        ]
    )

    assert len(
        small_boxes
    ) == 2

    assert all(
        item.verification_status
        == (
            VerificationStatus
            .NEEDS_CONFIRMATION
        )
        for item
        in small_boxes
    )

    small_box_ids = {
        item.id
        for item
        in small_boxes
    }

    assert not any(
        small_box_ids
        .intersection(
            set(
                group.item_ids
            )
        )
        for group
        in result.potential_duplicate_groups
    )

    assert (
        len(
            result.potential_duplicate_groups
        )
        == 1
    )

    print(
        "PENDING-DUPLICATE SUPPRESSION TEST: passed"
    )

    # ------------------------------------------------------------------
    # LOW CONFIDENCE
    # ------------------------------------------------------------------

    unknown = (
        items_by_name[
            "small black object"
        ][
            0
        ]
    )

    assert (
        unknown.verification_status
        == (
            VerificationStatus
            .NEEDS_CONFIRMATION
        )
    )

    assert (
        unknown.uncertainty_reason
        is not None
    )

    print(
        "LOW-CONFIDENCE CONFIRMATION TEST: passed"
    )

    # ------------------------------------------------------------------
    # PROVENANCE
    # ------------------------------------------------------------------

    provenance_by_id = {
        record.item_id:
            record
        for record
        in result.provenance
    }

    assert set(
        provenance_by_id[
            monitor.id
        ].observation_ids
    ) == {
        "f01_o01",
        "f02_o01",
    }

    assert (
        len(
            result.provenance
        )
        ==
        len(
            result.inventory.items
        )
    )

    print(
        "INVENTORY PROVENANCE TEST: passed"
    )

    print()

    print(
        "WALKTHROUGH INVENTORY NORMALIZER TEST: passed"
    )


if __name__ == "__main__":
    main()