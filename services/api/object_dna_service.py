import os

from dotenv import load_dotenv
from openai import OpenAI

from model_json import load_model_json
from object_dna_normalizer import normalize_object_dna_payload
from object_dna_sanitizer import sanitize_object_dna
from object_dna_validator import validate_object_dna
from schemas import InventoryItem, ObjectDNA


load_dotenv()

api_key = os.getenv("NEBIUS_API_KEY")

if not api_key:
    raise RuntimeError("NEBIUS_API_KEY was not found in .env")


client = OpenAI(
    base_url="https://api.tokenfactory.us-central1.nebius.com/v1/",
    api_key=api_key,
)


ALLOWED_PHYSICAL_TRAITS = """
flexible
rigid
soft
flat
hollow
foldable
stackable
movable
weighted
large_surface
small_surface
electrical
has_electrical_outlets
has_nozzle
opaque
portable
can_hold_liquid
can_dispense_liquid
""".strip()


ALLOWED_CAPABILITIES = """
support
elevate
contain
cover
hang
fasten
illuminate
reflect_light
diffuse_light
block_light
absorb_sound
dampen_sound
cushion
stack
fold
cut
organize
stabilize
provide_weight
provide_surface
provide_power_connection
reposition
dispense_liquid
""".strip()


def generate_object_dna(
    item: InventoryItem,
) -> ObjectDNA:
    response = client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b",
        reasoning_effort="low",

        response_format={
            "type": "json_object"
        },

        messages=[
            {
                "role": "user",
                "content": f"""
You are ZERO's Object DNA layer.

ZERO reasons about what physical objects CAN DO,
not merely their conventional names or purposes.

Analyze exactly ONE eligible canonical inventory object.

Return ONLY valid JSON in EXACTLY this structure:

{{
  "item_id": "{item.id}",
  "physical_traits": [
    {{
      "trait": "one allowed physical trait",
      "evidence_basis": "visually_observed | common_property | uncertain",
      "certainty": "high | medium | low",
      "note": "short grounded explanation"
    }}
  ],
  "affordances": [
    {{
      "capability": "one allowed capability",
      "description": "short grounded description",
      "evidence_basis": "visually_observed | common_property | uncertain",
      "certainty": "high | medium | low"
    }}
  ],
  "unknown_properties": [],
  "caution_notes": []
}}

Allowed physical traits:

{ALLOWED_PHYSICAL_TRAITS}

Allowed capabilities:

{ALLOWED_CAPABILITIES}


GENERAL RULES

- item_id MUST be exactly "{item.id}".

- Use EXACTLY the JSON field names shown above.

- Maximum 6 physical_traits.
- Maximum 5 affordances.
- Maximum 4 unknown_properties.
- Maximum 3 caution_notes.

- Do NOT consider a user goal.
- Do NOT propose a solution.
- Do NOT recommend buying anything.

- Physical traits describe WHAT THE OBJECT IS LIKE.
- Affordances describe WHAT THE OBJECT CAN USEFULLY HELP DO.

- Prefer a small number of strong reusable properties.
- Do not invent unusual edge-case uses merely because they are physically imaginable.
- Never output an affordance merely to say an object cannot do it.


EVIDENCE RULES

"visually_observed":
Use only when the supplied item description directly establishes the property.

"common_property":
Use for conservative ordinary knowledge of the clearly identified object.

"uncertain":
Use when plausible but not sufficiently established.


SEMANTIC RULES

"contain":
Requires a bounded interior capable of physically holding material or objects.

Do NOT use "contain" for:
- holding warmth
- supporting a person
- surrounding something externally
- containing internal components


"provide_surface":
Requires a genuinely useful PHYSICAL surface for placing, working on,
displaying, or supporting another physical object or material.

This capability is about physical placement geometry.

Do NOT use "provide_surface" merely because:
- every object has an exterior surface
- a monitor or screen displays visual information
- a device has a screen, panel, or user interface

A computer monitor showing images is NOT a provide_surface affordance merely
because its screen is called a display surface.


"support":
The object can realistically bear or hold another object,
material, or person in a useful way.

Do not invent load limits.


"elevate":
The object can meaningfully raise something to a higher physical level.


"stack":
The object can realistically participate in stable stacking.


"block_light":
Requires an opaque object with enough surface area to materially block light.


"reflect_light":
Requires a surface reasonably capable of useful light reflection.


"diffuse_light":
Requires material or construction reasonably capable of softening transmitted light.


"dampen_sound":
Soft, fibrous, or absorptive material may reduce reflected sound.

Do not imply certified acoustic performance.


"provide_power_connection":
Only genuine electrical receptacles or electrical connections.


"dispense_liquid":
Only a mechanism intended to release liquid.


CONTAINER / BOX RULES

For boxes, bins, baskets, bags, containers, drawers, and similar objects:

- "contain" may use conservative common knowledge when a bounded interior is
  established by the object type.

- Do NOT assume the container is empty.
  Current contents remain unknown unless explicitly established.

- Do NOT infer "provide_surface" merely because a box or container normally
  has a top.
  The supplied description must establish a usable physical top/lid/surface.

- Do NOT infer "support" or "elevate" merely because an object could
  theoretically be placed on top.
  Unknown closure state, structural condition, and load-bearing capacity
  matter.

- Do NOT infer "stack" or the "stackable" trait merely because the object is
  called a cardboard box.
  Stable stacking geometry must be sufficiently established.

- Do NOT assume a cardboard box is safely load-bearing.

- Do NOT assume a cardboard box can be flattened/folded unless its
  construction or ordinary identified type sufficiently supports that claim.

- When support, elevate, or stack is only plausible rather than established,
  OMIT the affordance instead of expressing unjustified confidence.

- Prefer omission over speculative physical reuse.


PHYSICAL TRAIT RULES

"has_electrical_outlets":
Only actual electrical receptacles.

A nozzle is NOT an electrical outlet.


"has_nozzle":
A physical nozzle for releasing or directing material such as liquid.


"can_hold_liquid":
Designed or conservatively known to hold liquid.


"can_dispense_liquid":
Has a mechanism capable of releasing liquid.


"flexible":
The object's body or material meaningfully bends or deforms.


"opaque":
Materially blocks visible light.


SAFETY / UNCERTAINTY RULES

Never invent exact:
- dimensions
- load limits
- electrical ratings
- chemical contents
- heat resistance
- structural strength
- material composition

For electrical objects:
- preserve unknown electrical rating
- preserve unknown electrical condition
- do not invent unrelated physical uses simply because technically possible

For liquid containers:
- preserve unknown current liquid contents

For spray bottles:
- do not infer what liquid they contain
- nozzle is NOT an electrical outlet

Do not invent medical or allergy warnings.


EXAMPLES TO OMIT

- power strip -> provide_surface
- power strip -> block_light
- chair -> contain
- blanket -> can_hold_liquid
- blanket -> dispense_liquid
- spray bottle -> support because it stands upright
- books -> contain because paper can fit between pages


QUALITY CHECK

Before returning every trait or affordance, ask:

"Would this genuinely help ZERO discover a realistic physical reuse later?"

If not, omit it.


Confirmed inventory item:

{item.model_dump_json(indent=2)}
""".strip(),
            }
        ],

        temperature=0,
        max_tokens=4000,
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        raise RuntimeError(
            f"Object DNA output was truncated for {item.id}."
        )

    message = choice.message

    if message.refusal:
        raise RuntimeError(
            f"Object DNA model refused {item.id}: {message.refusal}"
        )

    raw_output = message.content

    if not raw_output:
        raise RuntimeError(
            f"Object DNA model returned no final content for {item.id}."
        )

    payload = load_model_json(
        raw_output
    )

    normalized_payload = normalize_object_dna_payload(
        payload
    )

    result = ObjectDNA.model_validate(
        normalized_payload
    )

    result = sanitize_object_dna(
        result
    )

    result = validate_object_dna(
        result
    )

    if result.item_id != item.id:
        raise RuntimeError(
            f"Object DNA item mismatch. "
            f"Expected {item.id}, received {result.item_id}."
        )

    return result