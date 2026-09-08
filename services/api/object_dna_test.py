import os

from dotenv import load_dotenv
from openai import OpenAI

from model_json import parse_model_json
from object_dna_fixture import OBJECT_DNA_FIXTURE
from schemas import ObjectDNA, ObjectDNAResponse


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


all_object_dna: list[ObjectDNA] = []


for item in OBJECT_DNA_FIXTURE.items:
    response = client.chat.completions.create(
        model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",

        # Object DNA is a constrained classification/extraction task.
        # We do not need long hidden reasoning for this step.
        reasoning_effort="none",

        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "object_dna",
                "schema": ObjectDNA.model_json_schema(),
            },
        },

        messages=[
            {
                "role": "user",
                "content": f"""
You are ZERO's Object DNA layer.

ZERO is designed to reason about what physical objects CAN DO,
not merely what they are conventionally called or used for.

Analyze exactly ONE user-confirmed physical object.

Return ONE ObjectDNA JSON object matching the supplied response schema.

Allowed physical traits:

{ALLOWED_PHYSICAL_TRAITS}

Allowed capabilities:

{ALLOWED_CAPABILITIES}


CORE DISTINCTION

Physical traits describe WHAT THE OBJECT IS LIKE.

Examples:
- flexible
- rigid
- soft
- flat
- movable
- electrical
- has_nozzle

Affordances describe WHAT THE OBJECT CAN USEFULLY HELP DO.

Examples:
- support
- elevate
- cover
- provide_surface
- provide_power_connection
- dispense_liquid


GENERAL RULES

- item_id MUST be exactly "{item.id}".

- Maximum 6 physical_traits.
- Maximum 5 affordances.
- Maximum 4 unknown_properties.
- Maximum 3 caution_notes.

- Do NOT consider any user goal.
- Do NOT propose a solution.
- Do NOT recommend buying anything.

- Think beyond the object's conventional purpose,
  but remain physically conservative.

- Prefer a SMALL number of strong, reusable properties
  over many weak or technically possible ones.

- A trait or affordance should be included only if it could
  meaningfully help later physical problem-solving.

- Do NOT invent unusual edge-case capabilities just to fill
  the allowed vocabulary.

- Do NOT output a capability merely to say the object
  CANNOT do it.

Bad example:
{{
  "capability": "fold",
  "description": "This object cannot be folded."
}}

That capability should simply be omitted.


EVIDENCE RULES

Use "visually_observed" ONLY when the supplied item description
directly establishes the property.

Use "common_property" when the property comes from conservative,
ordinary knowledge of the clearly identified object type.

Use "uncertain" when the property is plausible but not sufficiently
established.

Do NOT label ordinary object knowledge as visually observed.

Example:
An office chair being able to support a seated person is normally
COMMON_PROPERTY unless the supplied description explicitly demonstrates
that load-bearing behavior.


CERTAINTY RULES

high:
strongly supported.

medium:
reasonable but meaningful uncertainty remains.

low:
weakly supported; use sparingly.


SEMANTIC DEFINITIONS

"contain":
The object has an actual bounded interior capable of physically holding
material or objects.

Do NOT use "contain" for:
- holding body heat
- supporting a person's body
- surrounding something externally
- merely containing components as part of its construction


"provide_surface":
The object provides a genuinely useful placement, work, display,
or support surface of meaningful size and geometry.

Do NOT use this merely because every physical object has an outer surface.


"support":
The object can realistically bear or hold another object, material,
or person in a useful way.

Do not assume unknown load limits.


"elevate":
The object can realistically raise something to a higher physical level.

Do not use this for trivial height differences.


"stack":
The object can realistically participate in stable stacking.

Do NOT assume:
- office chairs are stackable
- irregular containers are stackable
- something is stackable merely because another item could be placed on it


"block_light":
The object can materially obstruct light across a useful area.

A tiny opaque object does NOT qualify merely because it can cast a shadow.


"reflect_light":
The object's known or observed surface can meaningfully redirect light.

Do not infer reflective performance from an unknown material.


"diffuse_light":
The object can plausibly spread/transmit light more softly.

Do not infer this unless its material or construction reasonably supports it.


"dampen_sound":
The object's soft/fibrous/absorptive nature may reduce some reflected sound.

Do NOT imply certified acoustic performance.


"provide_power_connection":
The object provides genuine ELECTRICAL receptacles/connections.

Only use this for appropriate electrical objects.


"dispense_liquid":
The object has a mechanism intended to release liquid.

Do not generalize "dispense" to:
- warmth
- light
- sound
- energy
- information


PHYSICAL TRAIT DEFINITIONS

"has_electrical_outlets":
Only actual electrical receptacles.

A spray nozzle is NOT an electrical outlet.


"has_nozzle":
A physical nozzle used to release or direct material such as liquid.


"can_hold_liquid":
The object is designed or conservatively known to contain liquid.


"can_dispense_liquid":
The object has a mechanism that can release liquid.


"flexible":
The object's body or material meaningfully bends/deforms.

Do not call an object flexible unless the supplied description
or ordinary object knowledge supports it.


"opaque":
The object materially prevents visible light from passing through.

Do not infer opacity when material is unknown.


SAFETY AND UNKNOWN-PROPERTY RULES

Never invent exact:
- dimensions
- load limits
- electrical ratings
- chemical contents
- heat resistance
- structural strength
- material composition

If one of these matters but cannot be safely established,
put it in unknown_properties.

For electrical objects:
- preserve meaningful electrical uncertainty
- do not assume rating, condition, or remaining safe capacity

For containers:
- do not assume their current contents

For spray bottles specifically:
- do not assume what liquid they contain
- do not assume the bottle body is flexible unless supported
- do not call the nozzle an electrical outlet

Do not invent:
- medical warnings
- allergy warnings
- skin irritation claims
- inhalation claims

unless the confirmed object information actually supports such a concern.


QUALITY FILTER

Before returning each physical trait or affordance, ask:

"Would this information actually help a later ZERO planner discover
a realistic physical reuse?"

If NO, omit it.

Examples of things to OMIT:

- power strip -> provide_surface
- power strip -> block_light
- chair -> contain
- blanket -> dispense_liquid
- spray bottle -> support because it can stand on a table
- spray bottle -> fold when it does not fold
- books -> contain because pages sit inside covers


Confirmed inventory item:

{item.model_dump_json(indent=2)}
""".strip(),
            }
        ],

        temperature=0,
        max_completion_tokens=2200,
    )

    choice = response.choices[0]

    print(f"{item.id}: finish_reason={choice.finish_reason}")

    if choice.finish_reason == "length":
        raise RuntimeError(
            f"Object DNA output was truncated for {item.id}."
        )

    message = choice.message

    if message.refusal:
        raise RuntimeError(
            f"Object DNA model refused {item.id}: {message.refusal}"
        )

    # Normal structured-output responses usually arrive here.
    raw_output = message.content

    # Some Nemotron responses through the current Nebius deployment
    # expose their structured JSON payload through message.reasoning.
    if not raw_output:
        raw_output = getattr(message, "reasoning", None)

    if not raw_output:
        print()
        print(f"DEBUG response for {item.id}:")
        print(message.model_dump_json(indent=2))

        raise RuntimeError(
            f"Object DNA model returned no usable JSON payload for {item.id}."
        )

    result = parse_model_json(
        raw_output,
        ObjectDNA,
    )

    if result.item_id != item.id:
        raise RuntimeError(
            f"Object DNA item mismatch. "
            f"Expected {item.id}, received {result.item_id}."
        )

    all_object_dna.append(result)


combined = ObjectDNAResponse(
    objects=all_object_dna,
)


expected_ids = {
    item.id
    for item in OBJECT_DNA_FIXTURE.items
}

actual_ids = {
    item.item_id
    for item in combined.objects
}

if actual_ids != expected_ids:
    raise RuntimeError(
        "Final Object DNA set is incomplete. "
        f"Expected: {sorted(expected_ids)} "
        f"Received: {sorted(actual_ids)}"
    )


print()
print("Combined Object DNA:")
print(combined.model_dump_json(indent=2))