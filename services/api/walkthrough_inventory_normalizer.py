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
    Candidate inventory items that might actually refer to fewer
    physical objects than the resolver currently represents.

    We do NOT auto-merge these.

    Instead every member is placed behind NEEDS_CONFIRMATION.
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
# OBSERVATION-ID HELPERS
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
    match = OBSERVATION_ID_PATTERN.match(
        observation_id
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
    match = OBSERVATION_ID_PATTERN.match(
        observation_id
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
    """
    Use the earliest grounded observation ID as the stable identity
    anchor.

    Example:

        computer_monitor_f05_o01

    This is safer than numbered IDs such as computer_monitor_01,
    because excluding or inserting another item will not renumber all
    later inventory IDs.
    """

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
# CONSERVATIVE NON-INDEPENDENT-OBJECT FILTER
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
            candidate.canonical_name
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
    """
    Exclude only cases where we have strong deterministic evidence.

    Do NOT remove objects merely because they seem unimportant.

    ZERO is goal-independent at this stage.
    """

    name = (
        entity.canonical_name
        .strip()
        .lower()
    )

    description = (
        entity.canonical_description
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

    # Example from the real walkthrough:
    #
    # "drawers" with description:
    # "... integrated into the wardrobe"
    #
    # Only exclude this when the wardrobe itself is also observed in
    # the SAME frame. That gives us deterministic part-whole evidence.
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
# DUPLICATE-RISK NORMALIZATION
# ---------------------------------------------------------------------------


def _singularize_token(
    token: str,
) -> str:
    """
    Very deliberately small normalizer.

    This is not intended to be a general English stemmer.
    """

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

    # Small semantic aliases for object names that the perception model
    # frequently varies between views.
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


def _possible_duplicate(
    *,
    left: ResolvedPhysicalEntity,
    right: ResolvedPhysicalEntity,
) -> bool:
    """
    Identify candidate FALSE SPLITS.

    This never merges items.

    A positive result merely forces both candidates behind human
    confirmation so the planner cannot use both as independent physical
    resources until their multiplicity is established.
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

    # If both were observed in the same frame, they are physically
    # simultaneous and therefore distinct.
    if (
        left_frames
        & right_frames
    ):
        return False

    left_name = (
        _normalized_identity_name(
            left.canonical_name
        )
    )

    right_name = (
        _normalized_identity_name(
            right.canonical_name
        )
    )

    if (
        left_name
        != right_name
    ):
        return False

    # Matching normalized identity across non-overlapping frames is
    # enough to create a confirmation requirement.
    #
    # We intentionally DO NOT auto-merge here.
    return True


def _duplicate_groups(
    entities: list[
        ResolvedPhysicalEntity
    ],
    item_ids: dict[
        int,
        str,
    ],
) -> list[
    PotentialDuplicateGroup
]:
    """
    Build connected components of possible false-split relationships.

    Example:

        small_box_A ~ small_box_B
        small_box_B ~ small_box_C

    becomes one ambiguity group containing A/B/C.

    This does NOT claim all three are the same object. It means their
    multiplicity has not been established strongly enough for planning
    to treat all three as independent resources.
    """

    parent = {
        index:
            index
        for index
        in range(
            len(
                entities
            )
        )
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

    def union(
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

        new_root = min(
            root_left,
            root_right,
        )

        old_root = max(
            root_left,
            root_right,
        )

        parent[
            old_root
        ] = new_root

    for left_index in range(
        len(
            entities
        )
    ):
        for right_index in range(
            left_index + 1,
            len(
                entities
            ),
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
                union(
                    left_index,
                    right_index,
                )

    components: dict[
        int,
        list[int],
    ] = {}

    for index in range(
        len(
            entities
        )
    ):
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
                    "These candidates have the same "
                    "normalized physical identity but were "
                    "not observed simultaneously. Confirm "
                    "whether they are distinct objects before "
                    "using them independently."
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
# AMBIGUITY HELPERS
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


def _combine_uncertainty_reasons(
    reasons: list[str],
) -> str | None:
    cleaned = []

    for reason in reasons:
        reason = (
            reason.strip()
        )

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
    """
    Convert resolved walkthrough entities into ZERO's existing
    CanonicalInventory contract.

    Rules:

    1. Strongly evidenced non-independent details may be explicitly
       excluded.

    2. IDs are anchored to source observation IDs rather than list
       position.

    3. Low confidence remains NEEDS_CONFIRMATION.

    4. Ambiguous descriptions remain NEEDS_CONFIRMATION.

    5. Resolver identity uncertainty remains NEEDS_CONFIRMATION.

    6. Possible false splits remain NEEDS_CONFIRMATION until a user
       establishes that the candidates are genuinely distinct.

    No possible duplicates are automatically merged here.
    """

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

    duplicate_groups = (
        _duplicate_groups(
            retained_entities,
            item_ids,
        )
    )

    duplicate_item_ids = {
        item_id
        for group
        in duplicate_groups
        for item_id
        in group.item_ids
    }

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

        if (
            entity.identity_uncertainty
        ):
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

        if (
            item_id
            in duplicate_item_ids
        ):
            reasons.append(
                "This candidate may be a duplicate "
                "sighting of another inventory candidate; "
                "its physical multiplicity requires "
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

            provenance=(
                provenance
            ),

            excluded_entities=(
                excluded_entities
            ),

            potential_duplicate_groups=(
                duplicate_groups
            ),
        )
    )