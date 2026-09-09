import hashlib
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from json_format_repair import load_or_repair_json
from object_dna_fixture import OBJECT_DNA_FIXTURE
from object_dna_service import generate_object_dna
from plan_evaluator import evaluate_plan
from plan_normalizer import normalize_plan_payload
from plan_repair import repair_plan
from plan_schemas import PhysicalPlan
from plan_validator import (
    normalize_plan_item_ids,
    validate_inventory_grounding,
    validate_zero_plan,
)
from schemas import (
    CertaintyLevel,
    ObjectDNAResponse,
)
from semantic_critic import audit_plan_semantics


# ---------------------------------------------------------------------------
# CONSOLE ENCODING
# ---------------------------------------------------------------------------


def _configure_utf8_console() -> None:
    """
    Avoid Windows CP950/legacy-console failures when models return
    Unicode punctuation such as non-breaking hyphens.
    """

    for stream in (
        sys.stdout,
        sys.stderr,
    ):
        reconfigure = getattr(
            stream,
            "reconfigure",
            None,
        )

        if callable(reconfigure):
            try:
                reconfigure(
                    encoding="utf-8"
                )
            except Exception:
                pass


_configure_utf8_console()


# ---------------------------------------------------------------------------
# ENVIRONMENT / CLIENT
# ---------------------------------------------------------------------------


load_dotenv()

api_key = os.getenv("NEBIUS_API_KEY")

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

MAX_REPAIR_ATTEMPTS = 2


# ---------------------------------------------------------------------------
# PATHS / CACHE
# ---------------------------------------------------------------------------


REPO_ROOT = Path(
    __file__
).resolve().parents[2]

PRIVATE_CACHE_DIR = (
    REPO_ROOT
    / "sample_data"
    / "private"
)

OBJECT_DNA_CACHE_PATH = (
    PRIVATE_CACHE_DIR
    / "object_dna_fixture_cache.json"
)

OBJECT_DNA_CACHE_VERSION = 1


# ---------------------------------------------------------------------------
# EXPERIMENT
# ---------------------------------------------------------------------------


GOAL = """
Create a practical tabletop product-photography setup for photographing
a small object.

The user already has a phone camera.

Constraints:
- Budget: $0.
- Use only the listed physical inventory objects.
- Do not assume any unlisted lamp, window, tape, tripod, stand, shelf,
  fastener, table, tabletop, or other physical resource.
- No permanent modifications.
- Do not damage the listed objects.
- Prefer a simple setup that a normal person could actually assemble.
""".strip()


EXTERNAL_RESOURCES = [
    "phone camera",
]


inventory_payload = [
    {
        "id": item.id,
        "name": item.name,
        "description": item.description,
    }
    for item in OBJECT_DNA_FIXTURE.items
]


VALID_ITEM_IDS = {
    item["id"]
    for item in inventory_payload
}


# ---------------------------------------------------------------------------
# PLANNER CALL
# ---------------------------------------------------------------------------


def _request_plan(
    prompt: str,
    *,
    max_tokens: int,
):
    return client.chat.completions.create(
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
        max_tokens=max_tokens,
    )


def call_planner(
    prompt: str,
) -> PhysicalPlan:
    """
    Call the planner with enough room for Nemotron reasoning.

    If the first response still reaches the completion limit,
    retry once with stricter output compression.
    """

    response = _request_plan(
        prompt,
        max_tokens=6500,
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        print(
            "Planner output was truncated; "
            "retrying once with stricter compact output..."
        )

        compact_retry_prompt = (
            prompt
            + """

CRITICAL RETRY INSTRUCTION

The previous response exceeded the output budget.

Return the SAME kind of requested plan, but compress it aggressively:

- Maximum 4 steps.
- Maximum 18 words per action.
- Maximum 10 words per capability purpose.
- Maximum 15 words per why_it_helps.
- Maximum 3 assumptions.
- Maximum 3 unresolved risks.
- Maximum 4 constraint checks.
- Do not explain your reasoning.
- Do not repeat instructions.
- Return JSON only.
""".rstrip()
        )

        response = _request_plan(
            compact_retry_prompt,
            max_tokens=8000,
        )

        choice = response.choices[0]

        if choice.finish_reason == "length":
            raise RuntimeError(
                "Planner output was truncated "
                "after compact retry."
            )

    if choice.message.refusal:
        raise RuntimeError(
            f"Planner refused request: "
            f"{choice.message.refusal}"
        )

    raw_output = choice.message.content

    if not raw_output:
        raise RuntimeError(
            "Planner returned no final content."
        )

    payload = load_or_repair_json(
        raw_output
    )

    payload = normalize_plan_payload(
        payload
    )

    return PhysicalPlan.model_validate(
        payload
    )


# ---------------------------------------------------------------------------
# FIXED OBJECT DNA CACHE
# ---------------------------------------------------------------------------


def _fixture_fingerprint() -> str:
    """
    Fingerprint the canonical inventory fixture.

    If the fixture changes, the old Object DNA cache is not reused.
    """

    fixture_payload = (
        OBJECT_DNA_FIXTURE.model_dump(
            mode="json"
        )
    )

    canonical = json.dumps(
        fixture_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def _load_cached_object_dna(
) -> ObjectDNAResponse | None:
    if not OBJECT_DNA_CACHE_PATH.exists():
        return None

    try:
        envelope = json.loads(
            OBJECT_DNA_CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        if (
            envelope.get("cache_version")
            != OBJECT_DNA_CACHE_VERSION
        ):
            return None

        if (
            envelope.get("fixture_sha256")
            != _fixture_fingerprint()
        ):
            return None

        object_dna_payload = envelope.get(
            "object_dna"
        )

        return ObjectDNAResponse.model_validate(
            object_dna_payload
        )

    except Exception as exc:
        print(
            "Object DNA cache could not be reused; "
            f"regenerating. Reason: {exc}"
        )

        return None


def _save_object_dna_cache(
    object_dna: ObjectDNAResponse,
) -> None:
    PRIVATE_CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    envelope = {
        "cache_version":
            OBJECT_DNA_CACHE_VERSION,

        "fixture_sha256":
            _fixture_fingerprint(),

        "object_dna":
            object_dna.model_dump(
                mode="json"
            ),
    }

    OBJECT_DNA_CACHE_PATH.write_text(
        json.dumps(
            envelope,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def load_or_generate_object_dna(
) -> ObjectDNAResponse:
    cached = _load_cached_object_dna()

    if cached is not None:
        print(
            "Loading validated Object DNA "
            "from fixed fixture cache..."
        )

        return cached

    print(
        "Generating validated Object DNA..."
    )

    objects = []

    for item in OBJECT_DNA_FIXTURE.items:
        print(
            f"Generating DNA: {item.id}"
        )

        dna = generate_object_dna(
            item
        )

        objects.append(
            dna
        )

    object_dna = ObjectDNAResponse(
        objects=objects
    )

    _save_object_dna_cache(
        object_dna
    )

    print(
        "Saved validated Object DNA "
        "fixture cache."
    )

    return object_dna


# ---------------------------------------------------------------------------
# GENERIC BASELINE
# ---------------------------------------------------------------------------


baseline_prompt = f"""
You are solving a constrained physical problem.

Use creative but realistic reasoning.

Return ONLY valid JSON in EXACTLY this structure:

{{
  "title": "short plan title",
  "summary": "short summary",
  "item_ids_used": [
    "exact inventory ids"
  ],
  "steps": [
    {{
      "order": 1,
      "action": "specific physical action",
      "item_ids": [
        "exact inventory ids used in this step"
      ],
      "capability_uses": [],
      "why_it_helps": "brief reason"
    }}
  ],
  "assumptions": [],
  "unresolved_risks": [],
  "constraint_check": []
}}

Rules:
- Use only inventory item IDs provided below.
- Do not invent physical resources.
- Do not recommend purchasing anything.
- Do not assume an unlisted window, lamp, tripod, tape, stand,
  shelf, table, tabletop, fastener, or other physical object.
- The phone camera is already available and does not need an item ID.
- Maximum 8 steps.
- Be physically conservative.
- If something cannot be safely determined, state it in assumptions
  or unresolved_risks.
- Return JSON only.

Goal:

{GOAL}

Inventory:

{json.dumps(inventory_payload, indent=2)}
""".strip()


print(
    "Running generic baseline..."
)

baseline_plan = call_planner(
    baseline_prompt
)

baseline_plan = normalize_plan_item_ids(
    baseline_plan
)

validate_inventory_grounding(
    baseline_plan,
    VALID_ITEM_IDS,
)


# ---------------------------------------------------------------------------
# LOAD OR GENERATE FIXED VALIDATED OBJECT DNA
# ---------------------------------------------------------------------------


object_dna = (
    load_or_generate_object_dna()
)


# ---------------------------------------------------------------------------
# COMPACT CAPABILITY GRAPH
# ---------------------------------------------------------------------------


planner_dna_payload = []

for dna in object_dna.objects:
    planner_dna_payload.append(
        {
            "item_id":
                dna.item_id,

            "traits": [
                trait.trait.value
                for trait
                in dna.physical_traits
                if (
                    trait.certainty
                    != CertaintyLevel.LOW
                )
            ],

            "capabilities": [
                affordance.capability.value
                for affordance
                in dna.affordances
                if (
                    affordance.certainty
                    != CertaintyLevel.LOW
                )
            ],

            "unknown_properties":
                dna.unknown_properties,

            "caution_notes":
                dna.caution_notes,
        }
    )


# ---------------------------------------------------------------------------
# ZERO CAPABILITY-BOUND PLANNER
# ---------------------------------------------------------------------------


zero_prompt = f"""
You are ZERO's capability-bound physical planning layer.

You are NOT allowed to use an inventory object merely because you can
imagine a possible use for it.

Every physical use MUST be authorized by that item's validated Object DNA.

For every inventory item participating in a plan step, cite one or more
exact Object DNA capabilities authorizing that use.

Return ONLY valid JSON in EXACTLY this structure:

{{
  "title": "short plan title",
  "summary": "short grounded summary",
  "item_ids_used": [
    "exact inventory ids"
  ],
  "steps": [
    {{
      "order": 1,
      "action": "specific physical action",
      "item_ids": [
        "exact inventory ids used in this step"
      ],
      "capability_uses": [
        {{
          "item_id": "exact inventory id",
          "capability": "exact capability from that item's Object DNA",
          "purpose": "how this capability authorizes the physical use"
        }}
      ],
      "why_it_helps": "brief grounded reason"
    }}
  ],
  "assumptions": [],
  "unresolved_risks": [],
  "constraint_check": []
}}


HARD RULES

- Use only listed inventory IDs.

- Every inventory item used in a step must cite at least one validated
  Object DNA capability.

- The capability must exactly exist for that item.

- Do NOT invent capabilities.

- Do NOT infer a new physical use from object identity alone.

- Low-certainty capabilities are unavailable.

- Respect unknown_properties.

- Respect caution_notes.

- Do not convert an unknown property into an assumption just because
  it makes the plan easier.

- Do not claim physical properties that Object DNA does not establish.

Examples of forbidden unsupported claims:
- "non-slip" without friction evidence
- "well-lit" without illumination evidence
- "minimal shadow" without lighting evidence
- "stable" unless relevant stability is grounded
- "reflective" without reflect_light evidence
- "diffused light" without diffuse_light evidence

- Do not assume:
  lamp
  window
  tape
  tripod
  stand
  shelf
  table
  tabletop
  fastener
  or any other unlisted physical resource.

- The phone camera is explicitly available externally.

- Budget is $0.
- No permanent modifications.
- No intentional damage.

- Maximum 6 steps.
- Keep each action concise: maximum about 25 words.
- Keep each capability purpose concise: maximum about 15 words.
- Keep each why_it_helps concise: maximum about 20 words.
- Do not repeat Object DNA descriptions in the plan.

Return JSON only.


Goal:

{GOAL}


Canonical inventory:

{json.dumps(inventory_payload, indent=2)}


Validated capability graph:

{json.dumps(planner_dna_payload, indent=2)}
""".strip()


print(
    "Running capability-bound ZERO planner..."
)

zero_plan = call_planner(
    zero_prompt
)

zero_plan = normalize_plan_item_ids(
    zero_plan
)


print(
    "Running deterministic ZERO validation..."
)

zero_plan = validate_zero_plan(
    zero_plan,
    object_dna,
    VALID_ITEM_IDS,
)


# ---------------------------------------------------------------------------
# INITIAL SEMANTIC CRITIC
# ---------------------------------------------------------------------------


print(
    "Running ZERO semantic critic..."
)

critic_result = audit_plan_semantics(
    plan=zero_plan,
    goal=GOAL,
    inventory=OBJECT_DNA_FIXTURE.items,
    object_dna=object_dna,
    external_resources=EXTERNAL_RESOURCES,
)


# ---------------------------------------------------------------------------
# AUTOMATIC REPAIR LOOP
# ---------------------------------------------------------------------------


repair_attempt = 0


while (
    not critic_result.passed
    and repair_attempt
    < MAX_REPAIR_ATTEMPTS
):
    repair_attempt += 1

    print()

    print(
        f"ZERO semantic critic rejected plan. "
        f"Repair attempt {repair_attempt}/"
        f"{MAX_REPAIR_ATTEMPTS}..."
    )

    repaired_plan = repair_plan(
        plan=zero_plan,
        critic=critic_result,
        goal=GOAL,
        inventory=OBJECT_DNA_FIXTURE.items,
        object_dna=object_dna,
        external_resources=EXTERNAL_RESOURCES,
    )

    repaired_plan = normalize_plan_item_ids(
        repaired_plan
    )

    print(
        f"Running deterministic validation "
        f"after repair attempt "
        f"{repair_attempt}..."
    )

    repaired_plan = validate_zero_plan(
        repaired_plan,
        object_dna,
        VALID_ITEM_IDS,
    )

    print(
        f"Running semantic critic "
        f"after repair attempt "
        f"{repair_attempt}..."
    )

    repaired_critic = (
        audit_plan_semantics(
            plan=repaired_plan,
            goal=GOAL,
            inventory=(
                OBJECT_DNA_FIXTURE.items
            ),
            object_dna=object_dna,
            external_resources=(
                EXTERNAL_RESOURCES
            ),
        )
    )

    zero_plan = repaired_plan
    critic_result = repaired_critic


# ---------------------------------------------------------------------------
# NEUTRAL BASELINE VS ZERO EVALUATION
# ---------------------------------------------------------------------------


print()

print(
    "Running neutral evaluation "
    "of generic baseline..."
)

baseline_evaluation = evaluate_plan(
    plan=baseline_plan,
    goal=GOAL,
    inventory=OBJECT_DNA_FIXTURE.items,
    object_dna=object_dna,
    external_resources=EXTERNAL_RESOURCES,
)


print(
    "Running neutral evaluation "
    "of final ZERO plan..."
)

zero_evaluation = evaluate_plan(
    plan=zero_plan,
    goal=GOAL,
    inventory=OBJECT_DNA_FIXTURE.items,
    object_dna=object_dna,
    external_resources=EXTERNAL_RESOURCES,
)


# ---------------------------------------------------------------------------
# OUTPUT
# ---------------------------------------------------------------------------


print()
print("=" * 70)
print("GENERIC BASELINE")
print("=" * 70)

print(
    baseline_plan.model_dump_json(
        indent=2
    )
)


print()
print("=" * 70)
print("FINAL ZERO PLAN")
print("=" * 70)

print(
    zero_plan.model_dump_json(
        indent=2
    )
)


print()
print("=" * 70)
print("FINAL ZERO SEMANTIC CRITIC")
print("=" * 70)

print(
    critic_result.model_dump_json(
        indent=2
    )
)


print()
print("=" * 70)
print("ZERO REPAIR SUMMARY")
print("=" * 70)

print(
    f"Repair attempts used: "
    f"{repair_attempt}/"
    f"{MAX_REPAIR_ATTEMPTS}"
)


if critic_result.passed:
    print(
        "ZERO FINAL STATUS: ACCEPTED"
    )
else:
    print(
        "ZERO FINAL STATUS: REJECTED "
        "AFTER MAXIMUM REPAIR ATTEMPTS"
    )


print()
print("=" * 70)
print("NEUTRAL BASELINE EVALUATION")
print("=" * 70)

print(
    baseline_evaluation.model_dump_json(
        indent=2
    )
)


print()
print("=" * 70)
print("NEUTRAL ZERO EVALUATION")
print("=" * 70)

print(
    zero_evaluation.model_dump_json(
        indent=2
    )
)


print()
print("=" * 70)
print("BASELINE VS ZERO SUMMARY")
print("=" * 70)

print(
    "Baseline medium/high findings:",
    baseline_evaluation.medium_high_findings,
)

print(
    "ZERO medium/high findings:",
    zero_evaluation.medium_high_findings,
)

print(
    "Baseline accepted:",
    baseline_evaluation.accepted,
)

print(
    "ZERO accepted:",
    zero_evaluation.accepted,
)

print()

print(
    "Baseline issue counts:",
    {
        "unlisted_resource":
            baseline_evaluation.unlisted_resource_count,

        "unsupported_physical_claim":
            baseline_evaluation.unsupported_physical_claim_count,

        "unsupported_capability":
            baseline_evaluation.unsupported_capability_count,

        "hidden_assumption":
            baseline_evaluation.hidden_assumption_count,

        "safety_or_uncertainty":
            baseline_evaluation.safety_or_uncertainty_count,

        "constraint_violation":
            baseline_evaluation.constraint_violation_count,
    },
)

print(
    "ZERO issue counts:",
    {
        "unlisted_resource":
            zero_evaluation.unlisted_resource_count,

        "unsupported_physical_claim":
            zero_evaluation.unsupported_physical_claim_count,

        "unsupported_capability":
            zero_evaluation.unsupported_capability_count,

        "hidden_assumption":
            zero_evaluation.hidden_assumption_count,

        "safety_or_uncertainty":
            zero_evaluation.safety_or_uncertainty_count,

        "constraint_violation":
            zero_evaluation.constraint_violation_count,
    },
)