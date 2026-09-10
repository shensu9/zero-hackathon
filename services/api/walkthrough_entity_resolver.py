import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from json_format_repair import (
    load_or_repair_json,
)
from walkthrough_entity_resolution_schemas import (
    ResolvedPhysicalEntity,
    WalkthroughEntityResolution,
)
from walkthrough_entity_resolution_validator import (
    validate_entity_resolution,
)
from walkthrough_perception import (
    WalkthroughFrameObservation,
    WalkthroughObjectObservation,
)


MODEL = "nvidia/nemotron-3-super-120b-a12b"

BASE_URL = (
    "https://api.tokenfactory."
    "us-central1.nebius.com/v1/"
)

ALGORITHM_VERSION = 3

WINDOW_SIZE = 4
WINDOW_STRIDE = 2

MIN_LINK_CONFIDENCE = 0.85


REPO_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

CHUNK_CACHE_DIR = (
    REPO_ROOT
    / "sample_data"
    / "private"
    / "entity-resolution-chunk-cache"
)


# ---------------------------------------------------------------------------
# MODEL OUTPUT
# ---------------------------------------------------------------------------


class SameObjectLink(
    BaseModel,
):
    """
    Positive proposal that two cross-frame observations refer to the
    same physical object.
    """

    a: str = Field(
        min_length=1,
    )

    b: str = Field(
        min_length=1,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )


class WindowEntityLinks(
    BaseModel,
):
    """
    The model does NOT account for every observation.

    It reports positive identity matches only.

    Anything not linked automatically remains a separate physical
    entity.
    """

    links: list[
        SameObjectLink
    ] = Field(
        default_factory=list,
        max_length=100,
    )


# ---------------------------------------------------------------------------
# CLIENT
# ---------------------------------------------------------------------------


def _get_client() -> OpenAI:
    load_dotenv()

    api_key = os.getenv(
        "NEBIUS_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "NEBIUS_API_KEY was not found in .env"
        )

    return OpenAI(
        base_url=BASE_URL,
        api_key=api_key,
    )


# ---------------------------------------------------------------------------
# SOURCE HELPERS
# ---------------------------------------------------------------------------


def _observation_lookup(
    frames: list[
        WalkthroughFrameObservation
    ],
) -> dict[
    str,
    WalkthroughObjectObservation,
]:
    lookup = {}

    for frame in frames:
        for observation in frame.objects:
            observation_id = (
                observation.observation_id
            )

            if observation_id in lookup:
                raise RuntimeError(
                    "Duplicate source observation ID: "
                    f"{observation_id}"
                )

            lookup[
                observation_id
            ] = observation

    return lookup


def _frame_windows(
    frames: list[
        WalkthroughFrameObservation
    ],
) -> list[
    list[
        WalkthroughFrameObservation
    ]
]:
    """
    Build overlapping temporal windows.

    For eight keyframes:

        [1, 2, 3, 4]
        [3, 4, 5, 6]
        [5, 6, 7, 8]

    This gives continuity while keeping each reasoning problem small.
    """

    ordered = sorted(
        frames,
        key=lambda frame: (
            frame.sample_number
        ),
    )

    if not ordered:
        return []

    if (
        len(ordered)
        <= WINDOW_SIZE
    ):
        return [
            ordered
        ]

    last_start = (
        len(ordered)
        - WINDOW_SIZE
    )

    starts = list(
        range(
            0,
            last_start + 1,
            WINDOW_STRIDE,
        )
    )

    if (
        not starts
        or starts[-1]
        != last_start
    ):
        starts.append(
            last_start
        )

    windows = []

    for start in starts:
        window = ordered[
            start:
            start + WINDOW_SIZE
        ]

        windows.append(
            window
        )

    return windows


def _window_observation_text(
    frames: list[
        WalkthroughFrameObservation
    ],
) -> str:
    lines = []

    for frame in frames:
        for observation in frame.objects:
            name = " ".join(
                observation.name.split()
            )

            description = " ".join(
                observation.description.split()
            )

            location = " ".join(
                observation.location_hint.split()
            )

            lines.append(
                " | ".join(
                    [
                        observation.observation_id,
                        (
                            f"F"
                            f"{observation.frame_sample_number}"
                        ),
                        name,
                        description,
                        location,
                        (
                            f"C="
                            f"{observation.confidence:.2f}"
                        ),
                    ]
                )
            )

    return "\n".join(
        lines
    )


# ---------------------------------------------------------------------------
# PRIVATE CHUNK CACHE
# ---------------------------------------------------------------------------


def _resolver_source_sha256() -> str:
    path = Path(
        __file__
    ).resolve()

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def _cache_path_for_window(
    *,
    frames: list[
        WalkthroughFrameObservation
    ],
    observation_text: str,
) -> Path:
    payload = {
        "algorithm_version":
            ALGORITHM_VERSION,

        "model":
            MODEL,

        "resolver_source_sha256":
            _resolver_source_sha256(),

        "frame_numbers": [
            frame.sample_number
            for frame
            in frames
        ],

        "observations":
            observation_text,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
    ).encode(
        "utf-8"
    )

    digest = hashlib.sha256(
        serialized
    ).hexdigest()

    return (
        CHUNK_CACHE_DIR
        / f"links_{digest}.json"
    )


def _load_cached_window(
    path: Path,
) -> WindowEntityLinks | None:
    if not path.exists():
        return None

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        return (
            WindowEntityLinks
            .model_validate(
                payload
            )
        )

    except Exception:
        return None


def _save_cached_window(
    *,
    path: Path,
    result: WindowEntityLinks,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            result.model_dump(
                mode="json"
            ),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# WINDOW MODEL CALL
# ---------------------------------------------------------------------------


def _resolve_window(
    frames: list[
        WalkthroughFrameObservation
    ],
) -> tuple[
    WindowEntityLinks,
    bool,
]:
    observation_text = (
        _window_observation_text(
            frames
        )
    )

    cache_path = (
        _cache_path_for_window(
            frames=frames,
            observation_text=(
                observation_text
            ),
        )
    )

    cached = (
        _load_cached_window(
            cache_path
        )
    )

    if cached is not None:
        return (
            cached,
            True,
        )

    frame_numbers = [
        frame.sample_number
        for frame
        in frames
    ]

    prompt = f"""
You are ZERO's cross-frame physical identity matcher.

You receive object sightings from a SMALL TEMPORAL WINDOW of one
continuous room walkthrough.

Your ONLY task is to report POSITIVE pairs of observations that are
very likely sightings of the SAME real physical object.

Do not perform exhaustive accounting.

Do not output observations that have no match.

Do not output singleton objects.

Do not output canonical names, descriptions, explanations,
affordances, or plans.


Return ONLY valid JSON:

{{
  "links": [
    {{
      "a": "f05_o01",
      "b": "f06_o01",
      "confidence": 0.98
    }}
  ]
}}

If there are no sufficiently strong same-object matches:

{{
  "links": []
}}


======================================================================
CONSERVATIVE IDENTITY RULE
======================================================================

A false merge is worse than leaving two sightings separate.

Only output a link when confidence that they represent the SAME
physical object is at least {MIN_LINK_CONFIDENCE:.2f}.

If uncertain, omit the link.


======================================================================
CROSS-FRAME ONLY
======================================================================

a and b MUST come from DIFFERENT frames.

Never link two observations from the same frame.

Objects visible simultaneously are presumed physically distinct.


======================================================================
SAME NAME IS NOT ENOUGH
======================================================================

Do not link objects merely because their names match.

For example, three blankets visible in one area may be:

- beige blanket
- gray blanket
- cow-print blanket

They are distinct physical objects.


Likewise, two different shoe boxes remain different objects.


======================================================================
USE CONTEXT
======================================================================

Strong evidence can include:

- compatible appearance
- compatible color/form
- compatible location
- neighboring frames
- same desk/workstation context
- same surrounding objects
- distinctive shared description


Examples of plausible cross-frame identity:

- computer monitor seen from adjacent desk angles
- MIDI keyboard seen in neighboring room views
- same desk seen in consecutive views
- same toy car on the same shelf
- same bed from nearby angles


======================================================================
PARTS ARE NOT THE SAME OBJECT
======================================================================

Do not link a component to a larger object merely because it belongs
to it.

Examples:

wardrobe != drawer
bed != power cord
monitor != desk
pegboard != shelf

Entity normalization will deal with incidental/integrated components
later.


======================================================================
MINIMAL LINKS
======================================================================

If three sightings A, B, C clearly represent one physical object, you
do not need every possible pair.

A-B and B-C are enough.

Avoid redundant all-pairs output.


======================================================================
GROUNDING
======================================================================

Use ONLY observation IDs supplied below.

Never invent or alter IDs.


======================================================================
WINDOW
======================================================================

Frames:
{frame_numbers}

ID | FRAME | NAME | DESCRIPTION | LOCATION | CONFIDENCE

{observation_text}
""".strip()

    response = (
        _get_client()
        .chat.completions.create(
            model=MODEL,

            reasoning_effort="low",

            response_format={
                "type": "json_object"
            },

            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],

            temperature=0,

            # Output is now only positive links, normally a very small
            # response.
            max_tokens=2500,
        )
    )

    choice = response.choices[
        0
    ]

    if (
        choice.finish_reason
        == "length"
    ):
        raise RuntimeError(
            "Chunked entity-link output was truncated "
            f"for frames {frame_numbers}."
        )

    refusal = getattr(
        choice.message,
        "refusal",
        None,
    )

    if refusal:
        raise RuntimeError(
            "Chunked entity resolver refused: "
            f"{refusal}"
        )

    raw_output = (
        choice.message.content
    )

    if not raw_output:
        raise RuntimeError(
            "Chunked entity resolver returned "
            "no final content."
        )

    payload = load_or_repair_json(
        raw_output
    )

    result = (
        WindowEntityLinks
        .model_validate(
            payload
        )
    )

    _save_cached_window(
        path=cache_path,
        result=result,
    )

    return (
        result,
        False,
    )


# ---------------------------------------------------------------------------
# PROPOSAL VALIDATION
# ---------------------------------------------------------------------------


def _validate_link_proposals(
    *,
    window_frames: list[
        WalkthroughFrameObservation
    ],
    proposals: WindowEntityLinks,
) -> tuple[
    list[
        SameObjectLink
    ],
    int,
]:
    """
    Treat model links as proposals.

    Invalid, ungrounded, same-frame, and low-confidence proposals are
    safely discarded rather than allowed to mutate identity state.
    """

    lookup = _observation_lookup(
        window_frames
    )

    allowed_ids = set(
        lookup.keys()
    )

    valid_by_pair = {}

    rejected = 0

    for link in proposals.links:
        if (
            link.a not in allowed_ids
            or link.b not in allowed_ids
        ):
            rejected += 1
            continue

        if link.a == link.b:
            rejected += 1
            continue

        observation_a = lookup[
            link.a
        ]

        observation_b = lookup[
            link.b
        ]

        if (
            observation_a
            .frame_sample_number
            == observation_b
            .frame_sample_number
        ):
            rejected += 1
            continue

        if (
            link.confidence
            < MIN_LINK_CONFIDENCE
        ):
            rejected += 1
            continue

        a, b = sorted(
            (
                link.a,
                link.b,
            )
        )

        pair = (
            a,
            b,
        )

        normalized = (
            SameObjectLink(
                a=a,
                b=b,
                confidence=(
                    link.confidence
                ),
            )
        )

        existing = (
            valid_by_pair.get(
                pair
            )
        )

        if (
            existing is None
            or normalized.confidence
            > existing.confidence
        ):
            valid_by_pair[
                pair
            ] = normalized

    valid = sorted(
        valid_by_pair.values(),
        key=lambda link: (
            -link.confidence,
            link.a,
            link.b,
        ),
    )

    return (
        valid,
        rejected,
    )


# ---------------------------------------------------------------------------
# DETERMINISTIC UNION-FIND
# ---------------------------------------------------------------------------


def _build_components(
    *,
    frames: list[
        WalkthroughFrameObservation
    ],
    links: list[
        SameObjectLink
    ],
) -> tuple[
    list[
        list[str]
    ],
    list[
        SameObjectLink
    ],
    int,
]:
    """
    Construct physical-identity components from positive links.

    Safety invariant:

    A component may contain at most one observation from any source
    frame.

    Therefore a transitive merge cannot accidentally collapse two
    simultaneously visible objects into one entity.
    """

    lookup = _observation_lookup(
        frames
    )

    parent = {
        observation_id:
            observation_id
        for observation_id
        in lookup
    }

    frames_by_root = {
        observation_id: {
            observation
            .frame_sample_number
        }
        for (
            observation_id,
            observation,
        )
        in lookup.items()
    }

    def find(
        observation_id: str,
    ) -> str:
        root = (
            observation_id
        )

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
                observation_id
            ]
            != observation_id
        ):
            next_id = parent[
                observation_id
            ]

            parent[
                observation_id
            ] = root

            observation_id = (
                next_id
            )

        return root

    accepted_links = []

    conflict_rejections = 0

    ordered_links = sorted(
        links,
        key=lambda link: (
            -link.confidence,
            link.a,
            link.b,
        ),
    )

    for link in ordered_links:
        if (
            link.a not in lookup
            or link.b not in lookup
        ):
            # Should already be grounded, but keep the boundary safe.
            continue

        root_a = find(
            link.a
        )

        root_b = find(
            link.b
        )

        if root_a == root_b:
            continue

        if (
            frames_by_root[
                root_a
            ]
            & frames_by_root[
                root_b
            ]
        ):
            # Joining these components would create two sightings from
            # the same source frame inside one physical entity.
            conflict_rejections += 1
            continue

        # Deterministic root choice.
        new_root = min(
            root_a,
            root_b,
        )

        old_root = max(
            root_a,
            root_b,
        )

        parent[
            old_root
        ] = new_root

        frames_by_root[
            new_root
        ] = (
            frames_by_root[
                root_a
            ]
            | frames_by_root[
                root_b
            ]
        )

        if (
            old_root
            in frames_by_root
            and old_root
            != new_root
        ):
            del frames_by_root[
                old_root
            ]

        accepted_links.append(
            link
        )

    components_by_root = {}

    for observation_id in lookup:
        root = find(
            observation_id
        )

        components_by_root.setdefault(
            root,
            [],
        ).append(
            observation_id
        )

    def observation_sort_key(
        observation_id: str,
    ):
        observation = lookup[
            observation_id
        ]

        return (
            observation
            .frame_sample_number,

            observation_id,
        )

    components = []

    for component in (
        components_by_root.values()
    ):
        component.sort(
            key=observation_sort_key
        )

        components.append(
            component
        )

    components.sort(
        key=lambda component: (
            observation_sort_key(
                component[
                    0
                ]
            )
        )
    )

    return (
        components,
        accepted_links,
        conflict_rejections,
    )


# ---------------------------------------------------------------------------
# GROUNDED HYDRATION
# ---------------------------------------------------------------------------


def _representative_observation(
    *,
    observation_ids: list[str],
    lookup: dict[
        str,
        WalkthroughObjectObservation,
    ],
) -> WalkthroughObjectObservation:
    observations = [
        lookup[
            observation_id
        ]
        for observation_id
        in observation_ids
    ]

    observations.sort(
        key=lambda observation: (
            -observation.confidence,
            observation.frame_sample_number,
            observation.observation_id,
        )
    )

    return observations[
        0
    ]


def _component_merge_confidence(
    *,
    component: list[str],
    accepted_links: list[
        SameObjectLink
    ],
    representative: (
        WalkthroughObjectObservation
    ),
) -> float:
    if len(
        component
    ) == 1:
        return (
            representative
            .confidence
        )

    component_set = set(
        component
    )

    connecting_confidences = [
        link.confidence
        for link
        in accepted_links
        if (
            link.a in component_set
            and link.b in component_set
        )
    ]

    if not connecting_confidences:
        raise RuntimeError(
            "Multi-observation component has no "
            "accepted connecting links."
        )

    # Weakest accepted edge controls confidence for the chain.
    return min(
        connecting_confidences
    )


def _hydrate_components(
    *,
    frames: list[
        WalkthroughFrameObservation
    ],
    components: list[
        list[str]
    ],
    accepted_links: list[
        SameObjectLink
    ],
) -> WalkthroughEntityResolution:
    lookup = _observation_lookup(
        frames
    )

    entities = []

    for component in components:
        representative = (
            _representative_observation(
                observation_ids=(
                    component
                ),
                lookup=lookup,
            )
        )

        merge_confidence = (
            _component_merge_confidence(
                component=component,
                accepted_links=(
                    accepted_links
                ),
                representative=(
                    representative
                ),
            )
        )

        identity_uncertainty = None

        if (
            len(component) > 1
            and merge_confidence
            < 0.90
        ):
            identity_uncertainty = (
                "Cross-frame identity match "
                "remains somewhat uncertain."
            )

        entities.append(
            ResolvedPhysicalEntity(
                canonical_name=(
                    representative
                    .name
                    .strip()
                ),

                canonical_description=(
                    representative
                    .description
                    .strip()
                ),

                location_hint=(
                    representative
                    .location_hint
                    .strip()
                ),

                observation_ids=list(
                    component
                ),

                merge_confidence=(
                    merge_confidence
                ),

                identity_uncertainty=(
                    identity_uncertainty
                ),
            )
        )

    resolution = (
        WalkthroughEntityResolution(
            entities=entities,

            # Identity resolution no longer performs relevance/noise
            # filtering. Every unmerged sighting becomes a singleton.
            #
            # Canonical inventory normalization handles filtering in
            # the next layer.
            ignored_observations=[],
        )
    )

    return validate_entity_resolution(
        frames=frames,
        resolution=resolution,
    )


# ---------------------------------------------------------------------------
# PUBLIC SERVICE
# ---------------------------------------------------------------------------


def resolve_walkthrough_entities(
    frames: list[
        WalkthroughFrameObservation
    ],
) -> WalkthroughEntityResolution:
    """
    Chunked cross-frame physical identity resolution.

    Model:
        proposes only positive same-object links.

    Code:
        grounds links,
        rejects unsafe proposals,
        performs union-find,
        protects same-frame object identity,
        preserves all unmatched observations as singletons,
        hydrates metadata from perception,
        validates exact accounting.
    """

    if not frames:
        raise ValueError(
            "At least one walkthrough frame "
            "is required."
        )

    lookup = _observation_lookup(
        frames
    )

    if not lookup:
        raise ValueError(
            "Walkthrough contains no object observations."
        )

    windows = _frame_windows(
        frames
    )

    print(
        "Identity windows:",
        len(
            windows
        ),
    )

    proposals_by_pair = {}

    total_raw_proposals = 0
    total_rejected_proposals = 0

    model_calls = 0
    cache_hits = 0

    for window_index, window in enumerate(
        windows,
        start=1,
    ):
        frame_numbers = [
            frame.sample_number
            for frame
            in window
        ]

        print(
            f"  window "
            f"{window_index}/"
            f"{len(windows)} "
            f"frames {frame_numbers}"
        )

        result, cache_hit = (
            _resolve_window(
                window
            )
        )

        if cache_hit:
            cache_hits += 1

            print(
                "    CACHE HIT"
            )

        else:
            model_calls += 1

            print(
                "    Nemotron call complete"
            )

        total_raw_proposals += len(
            result.links
        )

        valid_links, rejected = (
            _validate_link_proposals(
                window_frames=window,
                proposals=result,
            )
        )

        total_rejected_proposals += (
            rejected
        )

        print(
            "    raw links:",
            len(
                result.links
            ),
        )

        print(
            "    grounded links:",
            len(
                valid_links
            ),
        )

        if rejected:
            print(
                "    rejected proposals:",
                rejected,
            )

        for link in valid_links:
            pair = tuple(
                sorted(
                    (
                        link.a,
                        link.b,
                    )
                )
            )

            existing = (
                proposals_by_pair.get(
                    pair
                )
            )

            if (
                existing is None
                or link.confidence
                > existing.confidence
            ):
                proposals_by_pair[
                    pair
                ] = link

    unique_links = list(
        proposals_by_pair.values()
    )

    components, accepted_links, conflicts = (
        _build_components(
            frames=frames,
            links=unique_links,
        )
    )

    print()
    print(
        "Chunk resolver model calls:",
        model_calls,
    )

    print(
        "Chunk resolver cache hits:",
        cache_hits,
    )

    print(
        "Raw link proposals:",
        total_raw_proposals,
    )

    print(
        "Rejected malformed/weak proposals:",
        total_rejected_proposals,
    )

    print(
        "Unique grounded links:",
        len(
            unique_links
        ),
    )

    print(
        "Accepted union links:",
        len(
            accepted_links
        ),
    )

    print(
        "Same-frame transitive conflicts rejected:",
        conflicts,
    )

    print(
        "Candidate physical entities:",
        len(
            components
        ),
    )

    return _hydrate_components(
        frames=frames,
        components=components,
        accepted_links=accepted_links,
    )