import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field

from json_format_repair import (
    load_or_repair_json,
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
        "https://api.tokenfactory.nebius.com/v1/"
    ),
    api_key=api_key,
)


MODEL = "MiniMaxAI/MiniMax-M3"

MAX_OBJECTS_PER_FRAME = 18


# ---------------------------------------------------------------------------
# SCHEMAS
# ---------------------------------------------------------------------------


class RawFrameObject(BaseModel):
    """
    One object observed in one video keyframe.

    This is perception only.
    No affordances or alternate uses belong here.
    """

    name: str = Field(
        min_length=1,
        max_length=100,
    )

    description: str = Field(
        min_length=1,
        max_length=400,
    )

    location_hint: str = Field(
        min_length=1,
        max_length=200,
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )


class RawFramePerception(BaseModel):
    objects: list[
        RawFrameObject
    ] = Field(
        default_factory=list,
        max_length=MAX_OBJECTS_PER_FRAME,
    )


class WalkthroughObjectObservation(BaseModel):
    observation_id: str

    frame_sample_number: int = Field(
        ge=1,
    )

    name: str

    description: str

    location_hint: str

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )


class WalkthroughFrameObservation(BaseModel):
    sample_number: int = Field(
        ge=1,
    )

    image_path: str

    objects: list[
        WalkthroughObjectObservation
    ]


# ---------------------------------------------------------------------------
# IMAGE ENCODING
# ---------------------------------------------------------------------------


def _image_to_data_url(
    image_path: Path,
) -> str:
    if not image_path.exists():
        raise FileNotFoundError(
            f"Image does not exist: {image_path}"
        )

    if not image_path.is_file():
        raise ValueError(
            f"Image path is not a file: {image_path}"
        )

    suffix = (
        image_path
        .suffix
        .lower()
    )

    if suffix in {
        ".jpg",
        ".jpeg",
    }:
        media_type = "image/jpeg"

    elif suffix == ".png":
        media_type = "image/png"

    elif suffix == ".webp":
        media_type = "image/webp"

    else:
        raise ValueError(
            "Unsupported perception image format: "
            f"{suffix}"
        )

    encoded = base64.b64encode(
        image_path.read_bytes()
    ).decode(
        "ascii"
    )

    return (
        f"data:{media_type};"
        f"base64,{encoded}"
    )


# ---------------------------------------------------------------------------
# PERCEPTION
# ---------------------------------------------------------------------------


def perceive_walkthrough_keyframe(
    image_path,
    *,
    sample_number: int,
) -> WalkthroughFrameObservation:
    """
    Detect physical objects visible in one walkthrough keyframe.

    Important:
    - goal-independent
    - no Object DNA reasoning
    - no cross-frame deduplication
    - no speculation about hidden properties
    """

    path = Path(
        image_path
    ).resolve()

    data_url = (
        _image_to_data_url(
            path
        )
    )

    prompt = f"""
You are ZERO's visual perception layer.

You are looking at ONE keyframe from a user's room walkthrough.

Your task is to identify distinct PHYSICAL OBJECTS that are actually
visible in the image.

This is OBJECT DISCOVERY only.

Do NOT decide how the objects could be repurposed.
Do NOT generate capabilities or affordances.
Do NOT solve a user goal.
Do NOT merge objects with anything from another frame.


Return ONLY valid JSON:

{{
  "objects": [
    {{
      "name": "specific common object name",
      "description": "brief visible physical description",
      "location_hint": "where it appears in this frame",
      "confidence": 0.95
    }}
  ]
}}


======================================================================
OBJECT NAMING
======================================================================

Use specific ordinary object identities whenever visually supportable.

GOOD:

- office chair
- desk
- computer monitor
- laptop
- computer keyboard
- mouse
- MIDI keyboard
- bed
- blanket
- pillow
- bookshelf
- rolling cart
- storage bin
- spray bottle
- power strip
- book
- bag
- jacket
- cable

Avoid vague names such as:

- thing
- object
- equipment
- furniture

when a more specific identity is visually clear.


======================================================================
WHAT TO INCLUDE
======================================================================

Include distinct visible objects that could reasonably matter to
physical planning later, including:

- furniture
- support surfaces
- portable household objects
- clothing and soft goods
- containers
- books
- bags
- electronics
- keyboards/controllers
- cables and power devices
- bottles
- boxes/bins
- chairs
- carts
- shelves
- bedding

Major fixed utilities may also be included when clearly visible and
potentially relevant without modification.


======================================================================
WHAT TO IGNORE
======================================================================

Do not waste object slots on:

- wall trim
- tiny screws
- door hinges
- tiny built-in hardware
- pixels/text displayed on a screen
- decorative visual patterns
- shadows
- reflections
- indistinct tiny clutter

unless the item is clearly a separate usable physical object.

Do not treat every component of one object as a separate object.

Example:

A computer monitor does not need separate detections for:
- screen
- bezel
- stand

unless there is a strong physical reason to treat them separately.


======================================================================
VISIBLE EVIDENCE ONLY
======================================================================

Describe only properties supported by the image.

Do NOT infer:

- hidden contents
- exact weight
- exact dimensions
- electrical rating
- chemical identity
- strength
- load capacity
- whether something is safe
- whether something is empty/full
- materials that cannot be visually established

Examples:

GOOD:
"translucent spray bottle with trigger nozzle"

BAD:
"water bottle containing harmless cleaning solution"


======================================================================
OBJECT GRANULARITY / PART-WHOLE RULE
======================================================================

ZERO needs an inventory of independently meaningful physical objects,
not a list of every visible component.

Prefer the complete object when a visible component is an integral
part of that object and is not normally useful independently.

Examples:

Prefer:
- bed

rather than simultaneously reporting:
- bed
- bed frame
- mattress edge

unless a component is clearly separate, removable, or independently
meaningful to physical planning.


Prefer:
- built-in wardrobe

rather than separately reporting an integrated drawer section merely
because the drawers are visually visible.


Prefer:
- computer monitor

rather than:
- monitor
- monitor stand
- monitor bezel


DO report removable or independently usable items separately.

Examples:

- blanket on a bed
- pillow
- fitted sheet
- clothes hanger
- power cord
- shoebox
- storage bin
- books
- laundry basket
- bag


Ignore tiny attached details that are unlikely to matter independently.

Examples:

- drawer pull tags
- small handle decorations
- hinges
- tiny clips attached to larger furniture
- screws
- trim


When uncertain between:
1. an integrated component of a larger object
2. a genuinely separate object

prefer the larger complete object unless the component is clearly
independent.


======================================================================
DUPLICATES INSIDE THIS FRAME
======================================================================

If several clearly separate objects of the same type are visible:

- report them separately when they are individually distinguishable
  and potentially meaningful

or

- describe them as a small group if individual separation is unclear

Do not invent an exact count when the image does not support one.


======================================================================
CONFIDENCE
======================================================================

Use confidence from 0.0 to 1.0.

High confidence:
identity is visually clear.

Medium confidence:
object is visible but exact subtype is uncertain.

Lower confidence:
identity is ambiguous.

Do not hide uncertainty by confidently guessing.


======================================================================
OUTPUT LIMIT
======================================================================

Maximum {MAX_OBJECTS_PER_FRAME} objects.

Prefer meaningful physical objects over tiny incidental details.

Return JSON only.
""".strip()

    response = client.chat.completions.create(
        model=MODEL,

        messages=[
            {
                "role": "user",

                "content": [
                    {
                        "type": "text",
                        "text": prompt,
                    },
                    {
                        "type": "image_url",

                        "image_url": {
                            "url": data_url,
                        },
                    },
                ],
            }
        ],

        response_format={
            "type": "json_object"
        },

        temperature=0,

        max_tokens=3500,
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        raise RuntimeError(
            "Walkthrough perception output "
            "was truncated."
        )

    if choice.message.refusal:
        raise RuntimeError(
            "Walkthrough perception refused: "
            f"{choice.message.refusal}"
        )

    raw_output = (
        choice.message.content
    )

    if not raw_output:
        raise RuntimeError(
            "Walkthrough perception returned "
            "no final content."
        )

    payload = load_or_repair_json(
        raw_output
    )

    raw_perception = (
        RawFramePerception
        .model_validate(
            payload
        )
    )

    observations = []

    for object_index, detected in enumerate(
        raw_perception.objects,
        start=1,
    ):
        observation_id = (
            f"f{sample_number:02d}_"
            f"o{object_index:02d}"
        )

        observations.append(
            WalkthroughObjectObservation(
                observation_id=(
                    observation_id
                ),

                frame_sample_number=(
                    sample_number
                ),

                name=(
                    detected.name.strip()
                ),

                description=(
                    detected.description.strip()
                ),

                location_hint=(
                    detected.location_hint.strip()
                ),

                confidence=(
                    detected.confidence
                ),
            )
        )

    return WalkthroughFrameObservation(
        sample_number=(
            sample_number
        ),

        image_path=(
            str(
                path
            )
        ),

        objects=(
            observations
        ),
    )