import re
from enum import Enum

from pydantic import BaseModel, Field

from inventory import (
    CONFIRMATION_THRESHOLD,
    slugify,
)
from schemas import (
    CanonicalInventory,
    InventoryItem,
    VerificationStatus,
)
from walkthrough_entity_resolution_schemas import (
    ResolvedPhysicalEntity,
    WalkthroughEntityResolution,
)


# ---------------------------------------------------------------------------
# OUTPUT / AUDIT SCHEMAS
# ---------------------------------------------------------------------------


class ExcludedEntityReason(
    str,
    Enum,
):
    TINY_INCIDENTAL_DETAIL = (
        "tiny_incidental_detail"
    )

    INTEGRATED_COMPONENT = (
        "integrated_component"
    )


class ExcludedResolvedEntity(
    BaseModel,
):
    name: str = Field(
        min_length=1,
        max_length=100,
    )

    observation_ids: list[str] = Field(
        min_length=1,
    )

    reason: ExcludedEntityReason

    explanation: str = Field(
        min_length=1,
        max_length=300,
    )


class InventoryItemProvenance(
    BaseModel,
):
    item_id: str = Field(
        min_length=1,
        max_length=100,
    )

    observation_ids: list[str] = Field(
        min_length=1,
    )

    resolution_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )


class PotentialDuplicateGroup(
    BaseModel,
):
    """
    Candidates that might represent fewer physical objects than the
    resolver currently believes.

    Only candidates that would otherwise be active planning resources
    participate in this check.
    """

    item_ids: list[str] = Field(
        min_length=2,
    )

    reason: str = Field(
        min_length=1,
        max_length=300,
    )


class WalkthroughInventoryNormalizationResult(
    BaseModel,
):
    inventory: CanonicalInventory

    provenance: list[
        InventoryItemProvenance
    ] = Field(
        default_factory=list,
    )

    excluded_entities: list[
        ExcludedResolvedEntity
    ] = Field(
        default_factory=list,
    )

    potential_duplicate_groups: list[
        PotentialDuplicateGroup
    ] = Field(
        default_factory=list,
    )


# ---------------------------------------------------------------------------
# OBSERVATION IDS
# ---------------------------------------------------------------------------


OBSERVATION_ID_PATTERN = re.compile(
    r"^f(?P<frame>\d+)_o(?P<object>\d+)$"
)


def _observation_sort_key(
    observation_id: str,
) -> tuple[
    int,
    int,
    str,
]:
    match = (
        OBSERVATION_ID_PATTERN
        .match(
            observation_id
        )
    )

    if match is None:
        return (
            10**9,
            10**9,
            observation_id,
        )

    return (
        int(
            match.group(
                "frame"
            )
        ),
        int(
            match.group(
                "object"
            )
        ),
        observation_id,
    )


def _frame_number(
    observation_id: str,
) -> int | None:
    match = (
        OBSERVATION_ID_PATTERN
        .match(
            observation_id
        )
    )

    if match is None:
        return None

    return int(
        match.group(
            "frame"
        )
    )


def _entity_frames(
    entity: ResolvedPhysicalEntity,
) -> set[int]:
    frames = set()

    for observation_id in (
        entity.observation_ids
    ):
        frame = _frame_number(
            observation_id
        )

        if frame is not None:
            frames.add(
                frame
            )

    return frames


def _anchor_observation_id(
    entity: ResolvedPhysicalEntity,
) -> str:
    return sorted(
        entity.observation_ids,
        key=_observation_sort_key,
    )[0]


# ---------------------------------------------------------------------------
# STABLE INVENTORY IDS
# ---------------------------------------------------------------------------


def _build_stable_item_id(
    entity: ResolvedPhysicalEntity,
) -> str:
    anchor = (
        _anchor_observation_id(
            entity
        )
    )

    base = slugify(
        entity.canonical_name
    )

    suffix = (
        f"_{anchor}"
    )

    maximum_base_length = (
        100
        - len(
            suffix
        )
    )

    base = (
        base[
            :maximum_base_length
        ]
        .rstrip(
            "_"
        )
    )

    if not base:
        base = "object"

    return (
        f"{base}"
        f"{suffix}"
    )


# ---------------------------------------------------------------------------
# NON-INDEPENDENT OBJECT FILTER
# ---------------------------------------------------------------------------


TINY_INCIDENTAL_NAMES = {
    "door hinge",
    "drawer pull tag",
}


def _find_same_frame_parent(
    *,
    entity: ResolvedPhysicalEntity,
    all_entities: list[
        ResolvedPhysicalEntity
    ],
    parent_name: str,
) -> bool:
    entity_frames = (
        _entity_frames(
            entity
        )
    )

    for candidate in all_entities:
        if candidate is entity:
            continue

        if (
            candidate
            .canonical_name
            .strip()
            .lower()
            != parent_name
        ):
            continue

        if (
            entity_frames
            & _entity_frames(
                candidate
            )
        ):
            return True

    return False


def _exclusion_for_entity(
    *,
    entity: ResolvedPhysicalEntity,
    all_entities: list[
        ResolvedPhysicalEntity
    ],
) -> ExcludedResolvedEntity | None:
    name = (
        entity
        .canonical_name
        .strip()
        .lower()
    )

    description = (
        entity
        .canonical_description
        .strip()
        .lower()
    )

    if name in TINY_INCIDENTAL_NAMES:
        return ExcludedResolvedEntity(
            name=(
                entity.canonical_name
            ),

            observation_ids=list(
                entity.observation_ids
            ),

            reason=(
                ExcludedEntityReason
                .TINY_INCIDENTAL_DETAIL
            ),

            explanation=(
                "This sighting is tiny attached hardware "
                "rather than an independently meaningful "
                "planning object."
            ),
        )

    if (
        name == "drawers"
        and "integrated" in description
        and "wardrobe" in description
        and _find_same_frame_parent(
            entity=entity,
            all_entities=all_entities,
            parent_name="wardrobe",
        )
    ):
        return ExcludedResolvedEntity(
            name=(
                entity.canonical_name
            ),

            observation_ids=list(
                entity.observation_ids
            ),

            reason=(
                ExcludedEntityReason
                .INTEGRATED_COMPONENT
            ),

            explanation=(
                "The sighting explicitly describes drawers "
                "integrated into a wardrobe that is already "
                "represented in the same frame."
            ),
        )

    return None


# ---------------------------------------------------------------------------
# IDENTITY NORMALIZATION
# ---------------------------------------------------------------------------


def _singularize_token(
    token: str,
) -> str:
    explicit = {
        "books": "book",
        "bottles": "bottle",
        "cables": "cable",
        "headphones": "headphone",
        "hangers": "hanger",
        "drawers": "drawer",
        "shoes": "shoe",
    }

    return explicit.get(
        token,
        token,
    )


def _normalized_identity_name(
    name: str,
) -> str:
    value = (
        slugify(
            name
        )
        .replace(
            "_",
            " ",
        )
    )

    tokens = [
        _singularize_token(
            token
        )
        for token
        in value.split()
    ]

    normalized = " ".join(
        tokens
    )

    aliases = {
        "nightstand":
            "bedside table",

        "side table":
            "bedside table",

        "small white side table":
            "bedside table",

        "bedside table":
            "bedside table",

        "shoe box":
            "shoe box",

        "shoebox":
            "shoe box",
    }

    return aliases.get(
        normalized,
        normalized,
    )


# ---------------------------------------------------------------------------
# BASE CONFIRMATION STATE
# ---------------------------------------------------------------------------


AMBIGUOUS_TEXT_MARKERS = (
    " or ",
    "possibly ",
    "possibly a ",
    "unidentified",
    "unclear",
)


def _description_is_ambiguous(
    entity: ResolvedPhysicalEntity,
) -> bool:
    text = (
        f"{entity.canonical_name} "
        f"{entity.canonical_description}"
    ).lower()

    return any(
        marker in text
        for marker
        in AMBIGUOUS_TEXT_MARKERS
    )


def _base_uncertainty_reasons(
    entity: ResolvedPhysicalEntity,
) -> list[str]:
    """
    Determine whether an entity already requires confirmation BEFORE
    considering multiplicity / false-split risk.
    """

    reasons = []

    if (
        entity.merge_confidence
        < CONFIRMATION_THRESHOLD
    ):
        reasons.append(
            "The perception/entity-resolution "
            "confidence is below the automatic "
            "acceptance threshold."
        )

    if entity.identity_uncertainty:
        reasons.append(
            entity.identity_uncertainty
        )

    if _description_is_ambiguous(
        entity
    ):
        reasons.append(
            "The visual identity description "
            "contains unresolved ambiguity."
        )

    return reasons


# ---------------------------------------------------------------------------
# ACTIVE-RESOURCE DUPLICATE PROTECTION
# ---------------------------------------------------------------------------


def _possible_duplicate(
    *,
    left: ResolvedPhysicalEntity,
    right: ResolvedPhysicalEntity,
) -> bool:
    """
    This function is called only for candidates that would otherwise
    be AUTO_ACCEPTED.

    It therefore protects active planning multiplicity without
    creating confirmation work for objects that are already withheld.
    """

    left_frames = (
        _entity_frames(
            left
        )
    )

    right_frames = (
        _entity_frames(
            right
        )
    )

    # Simultaneously observed objects are definitely physically
    # distinct.
    if (
        left_frames
        & right_frames
    ):
        return False

    return (
        _normalized_identity_name(
            left.canonical_name
        )
        ==
        _normalized_identity_name(
            right.canonical_name
        )
    )


def _duplicate_groups(
    *,
    entities: list[
        ResolvedPhysicalEntity
    ],
    item_ids: dict[
        int,
        str,
    ],
    eligible_indices: set[int],
) -> list[
    PotentialDuplicateGroup
]:
    """
    Duplicate ambiguity is relevant here only when BOTH candidates
    could otherwise reach downstream planning.

    Already-pending items cannot currently be double-counted by the
    planner, because ZERO's orchestrator excludes NEEDS_CONFIRMATION.
    """

    parent = {
        index:
            index
        for index
        in eligible_indices
    }

    frames_by_root = {
        index:
            _entity_frames(
                entities[
                    index
                ]
            )
        for index
        in eligible_indices
    }

    def find(
        index: int,
    ) -> int:
        root = index

        while (
            parent[
                root
            ]
            != root
        ):
            root = parent[
                root
            ]

        while (
            parent[
                index
            ]
            != index
        ):
            next_index = (
                parent[
                    index
                ]
            )

            parent[
                index
            ] = root

            index = (
                next_index
            )

        return root

    def union_if_safe(
        left: int,
        right: int,
    ) -> None:
        root_left = find(
            left
        )

        root_right = find(
            right
        )

        if (
            root_left
            == root_right
        ):
            return

        # Preserve the same physical invariant used by entity
        # resolution: an ambiguity component may not collapse two
        # objects that were simultaneously visible.
        if (
            frames_by_root[
                root_left
            ]
            &
            frames_by_root[
                root_right
            ]
        ):
            return

        new_root = min(
            root_left,
            root_right,
        )

        old_root = max(
            root_left,
            root_right,
        )

        merged_frames = (
            frames_by_root[
                root_left
            ]
            |
            frames_by_root[
                root_right
            ]
        )

        parent[
            old_root
        ] = new_root

        frames_by_root[
            new_root
        ] = merged_frames

        if (
            old_root
            in frames_by_root
        ):
            del frames_by_root[
                old_root
            ]

    ordered_indices = sorted(
        eligible_indices
    )

    for position, left_index in enumerate(
        ordered_indices
    ):
        for right_index in (
            ordered_indices[
                position + 1:
            ]
        ):
            if _possible_duplicate(
                left=(
                    entities[
                        left_index
                    ]
                ),
                right=(
                    entities[
                        right_index
                    ]
                ),
            ):
                union_if_safe(
                    left_index,
                    right_index,
                )

    components: dict[
        int,
        list[int],
    ] = {}

    for index in ordered_indices:
        root = find(
            index
        )

        components.setdefault(
            root,
            [],
        ).append(
            index
        )

    groups = []

    for indices in (
        components.values()
    ):
        if len(
            indices
        ) < 2:
            continue

        ids = [
            item_ids[
                index
            ]
            for index
            in indices
        ]

        groups.append(
            PotentialDuplicateGroup(
                item_ids=ids,

                reason=(
                    "These otherwise auto-accepted "
                    "candidates may refer to the same "
                    "physical object. Confirm multiplicity "
                    "before both can be used independently."
                ),
            )
        )

    groups.sort(
        key=lambda group: (
            group.item_ids[
                0
            ]
        )
    )

    return groups


# ---------------------------------------------------------------------------
# UNCERTAINTY TEXT
# ---------------------------------------------------------------------------


def _combine_uncertainty_reasons(
    reasons: list[str],
) -> str | None:
    cleaned = []

    for reason in reasons:
        reason = reason.strip()

        if (
            reason
            and reason
            not in cleaned
        ):
            cleaned.append(
                reason
            )

    if not cleaned:
        return None

    combined = " ".join(
        cleaned
    )

    return combined[
        :300
    ]


# ---------------------------------------------------------------------------
# PUBLIC NORMALIZER
# ---------------------------------------------------------------------------


def normalize_walkthrough_inventory(
    resolution: WalkthroughEntityResolution,
) -> WalkthroughInventoryNormalizationResult:
    all_entities = list(
        resolution.entities
    )

    retained_entities = []
    excluded_entities = []

    for entity in all_entities:
        exclusion = (
            _exclusion_for_entity(
                entity=entity,
                all_entities=(
                    all_entities
                ),
            )
        )

        if exclusion is not None:
            excluded_entities.append(
                exclusion
            )

        else:
            retained_entities.append(
                entity
            )

    # ------------------------------------------------------------------
    # STABLE IDS
    # ------------------------------------------------------------------

    item_ids: dict[
        int,
        str,
    ] = {}

    seen_item_ids = set()

    for index, entity in enumerate(
        retained_entities
    ):
        item_id = (
            _build_stable_item_id(
                entity
            )
        )

        if item_id in seen_item_ids:
            raise RuntimeError(
                "Walkthrough inventory generated "
                "duplicate stable item ID: "
                f"{item_id}"
            )

        seen_item_ids.add(
            item_id
        )

        item_ids[
            index
        ] = item_id

    # ------------------------------------------------------------------
    # BASE CONFIRMATION STATE
    # ------------------------------------------------------------------

    base_reasons_by_index = {
        index:
            _base_uncertainty_reasons(
                entity
            )
        for index, entity
        in enumerate(
            retained_entities
        )
    }

    # Only candidates with no existing uncertainty can currently reach
    # planning. Therefore only those candidates need immediate
    # duplicate-multiplicity protection.
    duplicate_eligible_indices = {
        index
        for index, reasons
        in base_reasons_by_index.items()
        if not reasons
    }

    duplicate_groups = (
        _duplicate_groups(
            entities=(
                retained_entities
            ),
            item_ids=item_ids,
            eligible_indices=(
                duplicate_eligible_indices
            ),
        )
    )

    duplicate_item_ids = {
        item_id
        for group
        in duplicate_groups
        for item_id
        in group.item_ids
    }

    # ------------------------------------------------------------------
    # FINAL INVENTORY
    # ------------------------------------------------------------------

    items = []
    provenance = []

    for index, entity in enumerate(
        retained_entities
    ):
        item_id = (
            item_ids[
                index
            ]
        )

        reasons = list(
            base_reasons_by_index[
                index
            ]
        )

        if (
            item_id
            in duplicate_item_ids
        ):
            reasons.append(
                "This otherwise auto-accepted candidate "
                "may duplicate another active inventory "
                "candidate; physical multiplicity requires "
                "confirmation."
            )

        if reasons:
            verification_status = (
                VerificationStatus
                .NEEDS_CONFIRMATION
            )

            uncertainty_reason = (
                _combine_uncertainty_reasons(
                    reasons
                )
            )

        else:
            verification_status = (
                VerificationStatus
                .AUTO_ACCEPTED
            )

            uncertainty_reason = None

        items.append(
            InventoryItem(
                id=item_id,

                name=(
                    entity.canonical_name
                ),

                description=(
                    entity
                    .canonical_description
                ),

                location_hint=(
                    entity.location_hint
                ),

                source_confidence=(
                    entity.merge_confidence
                ),

                verification_status=(
                    verification_status
                ),

                uncertainty_reason=(
                    uncertainty_reason
                ),
            )
        )

        provenance.append(
            InventoryItemProvenance(
                item_id=item_id,

                observation_ids=list(
                    entity.observation_ids
                ),

                resolution_confidence=(
                    entity.merge_confidence
                ),
            )
        )

    return (
        WalkthroughInventoryNormalizationResult(
            inventory=(
                CanonicalInventory(
                    items=items
                )
            ),

            provenance=provenance,

            excluded_entities=(
                excluded_entities
            ),

            potential_duplicate_groups=(
                duplicate_groups
            ),
        )
    )