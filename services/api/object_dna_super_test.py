import os

from dotenv import load_dotenv
from openai import OpenAI

from model_json import load_model_json
from object_dna_fixture import OBJECT_DNA_FIXTURE
from object_dna_normalizer import normalize_object_dna_payload
from object_dna_sanitizer import sanitize_object_dna
from object_dna_validator import validate_object_dna
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

Analyze exactly ONE user-confirmed physical object.

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
Requires a genuinely useful placement, work, display, or support surface.

Do not use it merely because every physical object has an exterior surface.


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

    print(f"{item.id}: finish_reason={choice.finish_reason}")

    if choice.finish_reason == "length":
        raise RuntimeError(
            f"Super Object DNA output was truncated for {item.id}."
        )

    message = choice.message

    if message.refusal:
        raise RuntimeError(
            f"Super model refused {item.id}: {message.refusal}"
        )

    raw_output = message.content

    if not raw_output:
        print()
        print(f"DEBUG Super response for {item.id}:")
        print(message.model_dump_json(indent=2))

        raise RuntimeError(
            f"Super returned no final content for {item.id}."
        )

    # 1. Parse raw JSON.
    payload = load_model_json(raw_output)

    # 2. Repair known provider/model field-name deviations.
    normalized_payload = normalize_object_dna_payload(
        payload
    )

    # 3. Enforce ZERO's Pydantic contract.
    result = ObjectDNA.model_validate(
        normalized_payload
    )

    # 4. Apply deterministic physical/safety guardrails.
    result = sanitize_object_dna(
        result
    )

    # 5. Verify the sanitized Object DNA still obeys hard rules.
    result = validate_object_dna(
        result
    )

    if result.item_id != item.id:
        raise RuntimeError(
            f"Object DNA item mismatch. "
            f"Expected {item.id}, received {result.item_id}."
        )

    all_object_dna.append(
        result
    )


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
        "Final Super Object DNA set is incomplete. "
        f"Expected: {sorted(expected_ids)} "
        f"Received: {sorted(actual_ids)}"
    )


print()
print("Combined Super Object DNA:")
print(
    combined.model_dump_json(
        indent=2
    )
)