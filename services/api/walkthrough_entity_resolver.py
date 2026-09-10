import json
import os

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from json_format_repair import (
    load_or_repair_json,
)
from walkthrough_entity_resolution_schemas import (
    IgnoredObservationReason,
    IgnoredWalkthroughObservation,
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


# ---------------------------------------------------------------------------
# COMPACT MODEL-OUTPUT CONTRACT
# ---------------------------------------------------------------------------


class CompactEntityGroup(
    BaseModel,
):
    """
    The model's only entity responsibility is deciding which
    observation IDs belong to the same physical object.
    """

    observation_ids: list[str] = Field(
        min_length=1,
        max_length=20,
    )

    merge_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )


class CompactIgnoredObservation(
    BaseModel,
):
    observation_id: str = Field(
        min_length=1,
    )

    reason: IgnoredObservationReason


class CompactEntityResolution(
    BaseModel,
):
    groups: list[
        CompactEntityGroup
    ] = Field(
        default_factory=list,
        max_length=100,
    )

    ignored: list[
        CompactIgnoredObservation
    ] = Field(
        default_factory=list,
        max_length=100,
    )


# ---------------------------------------------------------------------------
# CLIENT
# ---------------------------------------------------------------------------


def _get_client() -> OpenAI:
    """
    Create the Nebius client lazily.

    Importing this module therefore does not require an API call and
    local tests remain free.
    """

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
# SOURCE OBSERVATION HELPERS
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
                    "Source walkthrough contains "
                    "duplicate observation ID: "
                    f"{observation_id}"
                )

            lookup[
                observation_id
            ] = observation

    return lookup


def _compact_observations_text(
    frames: list[
        WalkthroughFrameObservation
    ],
) -> str:
    """
    Provide the resolver enough semantic evidence without sending
    pretty-printed JSON and schema-shaped repetition.

    Format:

        ID | FRAME | NAME | DESCRIPTION | LOCATION | CONFIDENCE
    """

    lines = []

    for frame in frames:
        for observation in frame.objects:
            description = " ".join(
                observation.description.split()
            )

            location = " ".join(
                observation.location_hint.split()
            )

            name = " ".join(
                observation.name.split()
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
# COMPACT ACCOUNTING VALIDATION
# ---------------------------------------------------------------------------


def _validate_compact_accounting(
    *,
    frames: list[
        WalkthroughFrameObservation
    ],
    compact: CompactEntityResolution,
) -> None:
    """
    Validate the compact model response BEFORE metadata hydration.

    Every source observation must occur exactly once:

        one group

    OR

        ignored

    Never both.
    Never neither.
    """

    lookup = _observation_lookup(
        frames
    )

    source_ids = set(
        lookup.keys()
    )

    grouped_ids = []

    for group in compact.groups:
        grouped_ids.extend(
            group.observation_ids
        )

    ignored_ids = [
        item.observation_id
        for item
        in compact.ignored
    ]

    # ---------------------------------------------------------------
    # DUPLICATE GROUP ASSIGNMENTS
    # ---------------------------------------------------------------

    if (
        len(
            set(
                grouped_ids
            )
        )
        != len(
            grouped_ids
        )
    ):
        duplicates = sorted(
            {
                observation_id
                for observation_id
                in grouped_ids
                if (
                    grouped_ids.count(
                        observation_id
                    )
                    > 1
                )
            }
        )

        raise RuntimeError(
            "Compact entity resolution assigned "
            "observations to multiple groups: "
            f"{duplicates}"
        )

    # ---------------------------------------------------------------
    # DUPLICATE IGNORE ASSIGNMENTS
    # ---------------------------------------------------------------

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

        raise RuntimeError(
            "Compact entity resolution duplicated "
            "ignored observations: "
            f"{duplicates}"
        )

    grouped_set = set(
        grouped_ids
    )

    ignored_set = set(
        ignored_ids
    )

    output_set = (
        grouped_set
        | ignored_set
    )

    # ---------------------------------------------------------------
    # UNKNOWN / INVENTED IDS
    # ---------------------------------------------------------------

    unknown_ids = sorted(
        output_set
        - source_ids
    )

    if unknown_ids:
        raise RuntimeError(
            "Compact entity resolution invented "
            "unknown observation IDs: "
            f"{unknown_ids}"
        )

    # ---------------------------------------------------------------
    # GROUPED + IGNORED AT ONCE
    # ---------------------------------------------------------------

    overlap = sorted(
        grouped_set
        & ignored_set
    )

    if overlap:
        raise RuntimeError(
            "Compact entity resolution both grouped "
            "and ignored observations: "
            f"{overlap}"
        )

    # ---------------------------------------------------------------
    # SILENTLY DROPPED
    # ---------------------------------------------------------------

    missing_ids = sorted(
        source_ids
        - output_set
    )

    if missing_ids:
        raise RuntimeError(
            "Compact entity resolution silently "
            "dropped source observations: "
            f"{missing_ids}"
        )


# ---------------------------------------------------------------------------
# DETERMINISTIC METADATA HYDRATION
# ---------------------------------------------------------------------------


def _representative_observation(
    *,
    observation_ids: list[str],
    lookup: dict[
        str,
        WalkthroughObjectObservation,
    ],
) -> WalkthroughObjectObservation:
    """
    Choose a grounded source observation to supply canonical metadata.

    Highest visual confidence wins.

    Ties:
        earlier frame
        then lexical observation ID
    """

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


def _ignored_explanation(
    reason: IgnoredObservationReason,
) -> str:
    explanations = {
        (
            IgnoredObservationReason
            .INTEGRATED_COMPONENT
        ): (
            "Perception sighting is treated as an "
            "integrated component of a larger retained object."
        ),

        (
            IgnoredObservationReason
            .TINY_INCIDENTAL_DETAIL
        ): (
            "Perception sighting is a tiny incidental "
            "detail unlikely to matter independently."
        ),

        (
            IgnoredObservationReason
            .NON_INDEPENDENT_PART
        ): (
            "Perception sighting is not treated as an "
            "independently meaningful physical object."
        ),

        (
            IgnoredObservationReason
            .LOW_CONFIDENCE_OR_AMBIGUOUS
        ): (
            "Perception sighting is too ambiguous or "
            "uncertain to retain as a physical entity."
        ),

        (
            IgnoredObservationReason
            .OTHER
        ): (
            "Perception sighting was explicitly excluded "
            "from the physical entity inventory."
        ),
    }

    return explanations[
        reason
    ]


def _hydrate_compact_resolution(
    *,
    frames: list[
        WalkthroughFrameObservation
    ],
    compact: CompactEntityResolution,
) -> WalkthroughEntityResolution:
    """
    Convert compact grouping decisions into the existing full
    WalkthroughEntityResolution contract.

    Names/descriptions/locations stay grounded in perception output
    instead of asking the resolver to rewrite them.
    """

    _validate_compact_accounting(
        frames=frames,
        compact=compact,
    )

    lookup = _observation_lookup(
        frames
    )

    entities = []

    for group in compact.groups:
        representative = (
            _representative_observation(
                observation_ids=(
                    group.observation_ids
                ),
                lookup=lookup,
            )
        )

        identity_uncertainty = None

        if (
            len(
                group.observation_ids
            )
            > 1
            and group.merge_confidence
            < 0.90
        ):
            identity_uncertainty = (
                "Cross-frame identity match "
                "remains somewhat uncertain."
            )

        entities.append(
            ResolvedPhysicalEntity(
                canonical_name=(
                    representative.name.strip()
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
                    group.observation_ids
                ),

                merge_confidence=(
                    group.merge_confidence
                ),

                identity_uncertainty=(
                    identity_uncertainty
                ),
            )
        )

    ignored = [
        IgnoredWalkthroughObservation(
            observation_id=(
                item.observation_id
            ),

            reason=(
                item.reason
            ),

            explanation=(
                _ignored_explanation(
                    item.reason
                )
            ),
        )
        for item
        in compact.ignored
    ]

    resolution = (
        WalkthroughEntityResolution(
            entities=entities,
            ignored_observations=ignored,
        )
    )

    # Keep the already-tested full validator as the final authority.
    return validate_entity_resolution(
        frames=frames,
        resolution=resolution,
    )


# ---------------------------------------------------------------------------
# MODEL RESOLUTION
# ---------------------------------------------------------------------------


def resolve_walkthrough_entities(
    frames: list[
        WalkthroughFrameObservation
    ],
) -> WalkthroughEntityResolution:
    """
    Resolve per-frame sightings into real physical objects.

    The model outputs ONLY identity grouping decisions.

    Existing grounded perception metadata is hydrated
    deterministically afterward.
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

    observation_text = (
        _compact_observations_text(
            frames
        )
    )

    prompt = f"""
You are ZERO's cross-frame PHYSICAL IDENTITY resolver.

You receive object sightings from sampled frames of ONE continuous
room walkthrough.

Your ONLY task is:

1. group sightings that refer to the SAME real physical object
2. preserve distinct physical objects as separate groups
3. explicitly ignore only incidental/non-independent sightings

Do NOT generate:

- canonical names
- descriptions
- locations
- Object DNA
- affordances
- plans
- explanations outside JSON

The application already has grounded metadata.
Your job is ONLY identity grouping.


======================================================================
OUTPUT
======================================================================

Return ONLY valid JSON in exactly this compact shape:

{{
  "groups": [
    {{
      "observation_ids": [
        "f05_o01",
        "f06_o01"
      ],
      "merge_confidence": 0.98
    }},
    {{
      "observation_ids": [
        "f02_o02"
      ],
      "merge_confidence": 0.99
    }}
  ],

  "ignored": [
    {{
      "observation_id": "f01_o06",
      "reason": "tiny_incidental_detail"
    }}
  ]
}}


Allowed ignored reasons:

- integrated_component
- tiny_incidental_detail
- non_independent_part
- low_confidence_or_ambiguous
- other


======================================================================
EXACT ACCOUNTING — CRITICAL
======================================================================

There are exactly {len(lookup)} source observation IDs.

EVERY source observation ID must occur EXACTLY ONCE.

Each ID must be:

A. inside exactly ONE group's observation_ids

OR

B. inside ignored

Never both.
Never neither.

Never invent an ID.
Never alter an ID.

A physical object seen only once MUST still receive its own
single-observation group.


======================================================================
MERGE CONSERVATIVELY
======================================================================

Merge sightings only when evidence makes it reasonably likely they
are the same real physical object.

Useful evidence:

- compatible identity
- distinctive appearance
- compatible colors/forms
- neighboring walkthrough frames
- same workspace or furniture context
- compatible surrounding objects

When uncertain, KEEP THEM SEPARATE.

A false merge is worse than a cautious duplicate.


======================================================================
SAME NAME != SAME PHYSICAL OBJECT
======================================================================

Do not merge simply because names match.

Example:

F2:
beige blanket

F2:
dark gray blanket

F2:
cow-print blanket

These are THREE separate objects.


Likewise:

red/white shoe box
green/white shoe box

are separate boxes unless later sightings provide strong evidence
for a cross-frame match.


======================================================================
SAME-FRAME RULE
======================================================================

Two observations from the SAME frame normally represent two different
physical objects.

Same-frame merging is exceptional and should occur only when perception
clearly duplicated one visible object.


======================================================================
EXPECTED CROSS-FRAME PATTERNS
======================================================================

Examples of reasonable merges IF the supplied evidence supports them:

computer monitor in adjacent desk views
    -> likely same monitor

MIDI keyboard in adjacent room views
    -> likely same MIDI keyboard

desk in adjacent workstation views
    -> likely same desk

toy car in adjacent workstation views
    -> likely same toy car

bed visible from multiple nearby angles
    -> likely same bed


Do not force these merges if the actual observation evidence conflicts.


======================================================================
INCIDENTAL / PART-WHOLE HANDLING
======================================================================

You MAY explicitly ignore sightings such as:

- door hinge
- drawer pull tag
- tiny attached hardware
- a clearly integrated component already represented by the complete
  larger physical object
- extremely ambiguous tiny clutter

Do NOT ignore independently meaningful removable objects merely
because they are small.

Generally retain:

- bags
- pouches
- bottles
- cables
- headphones
- books
- blankets
- pillows
- hangers
- shoe boxes
- storage bins
- clothing
- power devices


======================================================================
GROUP OBSERVATIONS
======================================================================

A source sighting such as:

- books
- bottles
- cables
- clothes hangers
- folded clothing

may already represent a visually unresolved group.

Treat that source observation as one observation entity.

Do NOT invent individual members or counts.


======================================================================
MERGE CONFIDENCE
======================================================================

For cross-frame groups:

0.90–1.00
strong same-object evidence

0.75–0.89
reasonable but uncertain

Below 0.75
prefer separate groups


For a singleton group, merge_confidence represents confidence that the
sighting should stand as its own entity rather than being merged with
another sighting.


======================================================================
TOKEN DISCIPLINE
======================================================================

Keep output extremely compact.

Do not repeat names.
Do not repeat descriptions.
Do not repeat locations.
Do not provide rationale.

Output IDs, merge confidence, and ignored reasons only.


======================================================================
SOURCE SIGHTINGS
======================================================================

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

            # Compact output should fit comfortably.
            # If this still truncates, the next architecture change
            # should be chunked resolution, not an unbounded increase.
            max_tokens=6000,
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
            "Compact walkthrough entity-resolution "
            "output was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            "Walkthrough entity resolution refused: "
            f"{choice.message.refusal}"
        )

    raw_output = (
        choice.message.content
    )

    if not raw_output:
        raise RuntimeError(
            "Walkthrough entity resolution returned "
            "no final content."
        )

    payload = load_or_repair_json(
        raw_output
    )

    compact = (
        CompactEntityResolution
        .model_validate(
            payload
        )
    )

    return _hydrate_compact_resolution(
        frames=frames,
        compact=compact,
    )