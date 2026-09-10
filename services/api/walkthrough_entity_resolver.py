import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from json_format_repair import (
    load_or_repair_json,
)
from walkthrough_entity_resolution_schemas import (
    WalkthroughEntityResolution,
)
from walkthrough_entity_resolution_validator import (
    validate_entity_resolution,
)
from walkthrough_perception import (
    WalkthroughFrameObservation,
)


load_dotenv()

api_key = os.getenv(
    "NEBIUS_API_KEY"
)

if not api_key:
    raise RuntimeError(
        "NEBIUS_API_KEY was not found in .env"
    )


client = OpenAI(
    base_url=(
        "https://api.tokenfactory."
        "us-central1.nebius.com/v1/"
    ),
    api_key=api_key,
)


MODEL = "nvidia/nemotron-3-super-120b-a12b"


def _compact_observations(
    frames: list[
        WalkthroughFrameObservation
    ],
) -> list[dict]:
    observations = []

    for frame in frames:
        for observation in frame.objects:
            observations.append(
                {
                    "observation_id":
                        observation.observation_id,

                    "frame":
                        observation.frame_sample_number,

                    "name":
                        observation.name,

                    "description":
                        observation.description,

                    "location_hint":
                        observation.location_hint,

                    "confidence":
                        observation.confidence,
                }
            )

    return observations


def resolve_walkthrough_entities(
    frames: list[
        WalkthroughFrameObservation
    ],
) -> WalkthroughEntityResolution:
    """
    Resolve per-frame object sightings into candidate real-world
    physical entities.

    Semantic merge decisions come from the reasoning model.

    Exact observation accounting is enforced deterministically
    afterward.
    """

    if not frames:
        raise ValueError(
            "At least one walkthrough frame "
            "is required."
        )

    observations = (
        _compact_observations(
            frames
        )
    )

    if not observations:
        raise ValueError(
            "Walkthrough contains no object observations."
        )

    response = client.chat.completions.create(
        model=MODEL,
        reasoning_effort="low",

        response_format={
            "type": "json_object"
        },

        messages=[
            {
                "role": "user",
                "content": f"""
You are ZERO's cross-frame physical entity resolver.

You receive object observations from multiple sampled frames of ONE
continuous room walkthrough.

Each observation is a sighting.

Your task is to determine which sightings refer to the SAME real
physical object and produce candidate physical entities.

This is ENTITY RESOLUTION only.

Do NOT generate Object DNA.
Do NOT generate affordances.
Do NOT solve a user goal.
Do NOT invent objects that were never observed.


Return ONLY valid JSON:

{{
  "entities": [
    {{
      "canonical_name":
        "specific ordinary physical object name",

      "canonical_description":
        "brief description combining only visible evidence",

      "location_hint":
        "concise approximate room/location description",

      "observation_ids": [
        "exact source observation IDs belonging to this object"
      ],

      "merge_confidence":
        0.95,

      "identity_uncertainty":
        null
    }}
  ],

  "ignored_observations": [
    {{
      "observation_id":
        "exact source observation ID",

      "reason":
        "integrated_component | tiny_incidental_detail | non_independent_part | low_confidence_or_ambiguous | other",

      "explanation":
        "brief reason for ignoring this sighting"
    }}
  ]
}}


======================================================================
CRITICAL ACCOUNTING RULE
======================================================================

EVERY source observation ID must appear EXACTLY ONCE.

It must appear either:

1. inside exactly one entity's observation_ids

OR

2. inside ignored_observations

Never both.
Never neither.

Never invent observation IDs.

Do not alter observation IDs.


======================================================================
MERGE CONSERVATIVELY
======================================================================

Two sightings should be merged only when the available evidence makes
it reasonably likely they are the same physical object.

Useful evidence includes:

- same distinctive appearance
- same color/form
- compatible location
- neighboring walkthrough frames
- same surrounding objects
- same furniture/workspace context
- descriptions that clearly refer to one persistent object

If identity is uncertain, prefer keeping sightings separate rather
than incorrectly merging two real objects.

False merges are worse than cautious duplicates.


======================================================================
SAME NAME DOES NOT MEAN SAME OBJECT
======================================================================

Multiple objects may share the same ordinary name.

Example:

One frame visibly contains:

- beige blanket
- gray blanket
- cow-print blanket

These are THREE physical objects.

Do NOT merge them merely because each may be named "blanket".


Example:

One frame contains:

- red/white shoe box
- green/white shoe box

These are TWO physical objects.


======================================================================
CROSS-FRAME MERGE EXAMPLES
======================================================================

LIKELY SAME:

Frame 5:
"computer monitor"
black monitor on desk

Frame 6:
"computer monitor"
same desk/workspace and compatible appearance

This may be one physical monitor.


LIKELY SAME:

Frame 3:
"MIDI keyboard"

Frame 4:
"MIDI keyboard"

Adjacent room views show the same keyboard/workstation.


DO NOT MERGE:

Frame 2:
"blanket"
beige plush blanket

Frame 2:
"blanket"
dark gray plush blanket

They are simultaneously visible and physically distinct.


======================================================================
SIMULTANEOUS OBSERVATIONS
======================================================================

If two observations occur in the SAME frame, they normally represent
two separate physical objects.

Do NOT merge two same-frame observations into one entity unless they
are clearly duplicate descriptions of exactly the same visible object.

Treat same-frame merging as exceptional.


======================================================================
PART-WHOLE / INCIDENTAL OBSERVATIONS
======================================================================

The perception model may occasionally report an integral component or
tiny detail as though it were a separate object.

These may be ignored explicitly.

Examples that may be ignored when appropriate:

- door hinge
- drawer pull tag
- tiny attached furniture hardware
- integral wardrobe drawer section when the wardrobe itself represents
  the useful physical structure
- small unidentified decorative detail


Do NOT ignore removable, independently usable objects merely because
they are small.

Examples that should generally remain entities:

- pouch
- bag
- bottle
- cable
- headphones
- book
- shoe box
- storage bin
- pillow
- blanket
- hanger


======================================================================
FIXED ENVIRONMENT OBJECTS
======================================================================

Do not automatically ignore a physical object just because it is fixed.

Objects such as:

- wall outlet
- window
- wardrobe
- shelf

may matter to future planning and should remain if they are meaningful
physical features.

Tiny structural hardware may still be ignored.


======================================================================
GROUP OBSERVATIONS
======================================================================

Some observations describe a group rather than one individually
identified item.

Examples:

- books
- folded clothing
- clothes hangers
- hanging clothes
- cables
- bottles

If perception does not distinguish the individual members clearly,
preserve the group as one entity rather than inventing exact individual
objects.

Do not fabricate counts.


======================================================================
CANONICAL NAME
======================================================================

Use the most specific ordinary identity supported across observations.

Examples:

GOOD:
- computer monitor
- MIDI keyboard
- mechanical keyboard
- office desk
- beige plush blanket
- rolling cart
- plastic storage bin
- laundry basket

Avoid overly vague names when evidence supports a more specific one.


======================================================================
CANONICAL DESCRIPTION
======================================================================

Combine only visible evidence.

Do NOT infer:

- hidden contents
- exact mass
- electrical rating
- chemical identity
- load capacity
- safety
- ownership
- dimensions not observed

Keep description to roughly 25 words or fewer.


======================================================================
LOCATION HINT
======================================================================

Describe the approximate scene location consistently.

Examples:

- bed area
- desk/workstation
- wardrobe area
- floor beside wardrobe
- rolling-cart/storage area

Do not pretend you know exact coordinates.


======================================================================
MERGE CONFIDENCE
======================================================================

0.90–1.00:
strong evidence sightings represent the same physical object.

0.75–0.89:
reasonable match but some uncertainty remains.

Below 0.75:
prefer separate entities unless there is a compelling reason to merge.

Single-observation entities may have high identity confidence if the
object itself is visually clear.


======================================================================
IDENTITY UNCERTAINTY
======================================================================

Use null when identity is sufficiently clear.

Use a short statement when something important remains uncertain.

Examples:

"Could be the same small box seen in frame 5, but evidence is weak."

"Exact subtype of bag is unclear."

Do not use this field merely to restate low visual confidence.


======================================================================
OUTPUT DISCIPLINE
======================================================================

- Keep output compact.
- Maximum 100 entities.
- Maximum 100 ignored observations.
- Do not repeat source descriptions verbatim unnecessarily.
- Do not explain reasoning outside JSON.
- Return JSON only.


======================================================================
SOURCE OBSERVATIONS
======================================================================

{json.dumps(observations, indent=2, ensure_ascii=False)}
""".strip(),
            }
        ],

        temperature=0,
        max_tokens=8000,
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        raise RuntimeError(
            "Walkthrough entity-resolution output "
            "was truncated."
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

    resolution = (
        WalkthroughEntityResolution
        .model_validate(
            payload
        )
    )

    return validate_entity_resolution(
        frames=frames,
        resolution=resolution,
    )