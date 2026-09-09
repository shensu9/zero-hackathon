import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from benchmark_cases import BenchmarkCase
from critic_schemas import (
    CriticIssueType,
    CriticSeverity,
    PlanCriticFinding,
    PlanCriticResult,
)
from evaluation_schemas import PlanEvaluation
from json_format_repair import load_or_repair_json
from object_dna_fixture import OBJECT_DNA_FIXTURE
from object_dna_service import generate_object_dna
from plan_evaluator import evaluate_plan
from plan_normalizer import (
    normalize_external_resource_ids,
    normalize_plan_payload,
)
from plan_repair import repair_plan
from plan_schemas import PhysicalPlan
from plan_validator import (
    PlanValidationError,
    normalize_plan_item_ids,
    validate_inventory_grounding,
    validate_zero_plan,
)
from schemas import (
    CertaintyLevel,
    ObjectDNAResponse,
)
from semantic_critic import audit_plan_semantics


load_dotenv()

api_key = os.getenv("NEBIUS_API_KEY")

if not api_key:
    raise RuntimeError(
        "NEBIUS_API_KEY was not found in .env"
    )


client = OpenAI(
    base_url="https://api.tokenfactory.us-central1.nebius.com/v1/",
    api_key=api_key,
)


MODEL = "nvidia/nemotron-3-super-120b-a12b"

MAX_REPAIR_ATTEMPTS = 2
MAX_PLAN_STEPS = 6


# ---------------------------------------------------------------------------
# PATHS / FIXED INVENTORY
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parents[2]

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


INVENTORY_PAYLOAD = [
    {
        "id": item.id,
        "name": item.name,
        "description": item.description,
    }
    for item in OBJECT_DNA_FIXTURE.items
]


VALID_ITEM_IDS = {
    item["id"]
    for item in INVENTORY_PAYLOAD
}


# ---------------------------------------------------------------------------
# RESULT TYPE
# ---------------------------------------------------------------------------


@dataclass
class CaseRunResult:
    case_id: str
    case_name: str
    expectation: str

    baseline_plan: PhysicalPlan

    zero_initial_plan: PhysicalPlan
    zero_initial_critic: PlanCriticResult

    zero_final_plan: PhysicalPlan
    zero_final_critic: PlanCriticResult

    repair_attempts: int
    repair_validation_failures: int

    baseline_evaluation: PlanEvaluation
    zero_evaluation: PlanEvaluation


# ---------------------------------------------------------------------------
# MODEL PLAN CALL
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
    Generate one physical plan.

    If the first response reaches the output limit,
    retry once with stricter compression.
    """

    response = _request_plan(
        prompt,
        max_tokens=6500,
    )

    choice = response.choices[0]

    if choice.finish_reason == "length":
        print(
            "Planner output was truncated; "
            "retrying once with compact output..."
        )

        compact_prompt = (
            prompt
            + f"""

CRITICAL RETRY INSTRUCTION

The previous response exceeded the output budget.

Return the same requested plan, but compress it aggressively:

- Maximum {MAX_PLAN_STEPS} steps.
- Maximum 18 words per action.
- Maximum 10 words per capability purpose.
- Maximum 15 words per why_it_helps.
- Maximum 3 assumptions.
- Maximum 3 unresolved risks.
- Maximum 4 constraint checks.
- Do not explain reasoning.
- Do not repeat instructions.
- Return JSON only.
""".rstrip()
        )

        response = _request_plan(
            compact_prompt,
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
# OBJECT DNA CACHE
# ---------------------------------------------------------------------------


def _fixture_fingerprint() -> str:
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

        payload = envelope.get(
            "object_dna"
        )

        return ObjectDNAResponse.model_validate(
            payload
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
# CAPABILITY GRAPH
# ---------------------------------------------------------------------------


def build_compact_capability_graph(
    object_dna: ObjectDNAResponse,
) -> list[dict]:
    result = []

    for dna in object_dna.objects:
        result.append(
            {
                "item_id":
                    dna.item_id,

                "traits": [
                    trait.trait.value
                    for trait in dna.physical_traits
                    if (
                        trait.certainty
                        != CertaintyLevel.LOW
                    )
                ],

                "capabilities": [
                    affordance.capability.value
                    for affordance in dna.affordances
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

    return result


# ---------------------------------------------------------------------------
# BASELINE PROMPT
# ---------------------------------------------------------------------------


def build_baseline_prompt(
    case: BenchmarkCase,
) -> str:
    external_resources = list(
        case.external_resources
    )

    return f"""
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

RULES

- Use only canonical inventory objects and explicit external resources.

- External resources may be used without inventory IDs.

- Never assign an inventory ID to an external resource.

- Do not invent additional physical resources.

- Do not recommend purchasing anything unless the goal explicitly
  permits it.

- Respect every constraint written in the goal.

- Be physically conservative.

- If a physical property is unknown, do not silently assume it.

- If something cannot be safely determined, preserve that uncertainty
  in assumptions or unresolved_risks.

- Maximum {MAX_PLAN_STEPS} steps.

- Keep actions and explanations concise.

- Return JSON only.


GOAL

{case.goal}


EXPLICIT EXTERNAL RESOURCES

{json.dumps(external_resources, indent=2)}


CANONICAL INVENTORY

{json.dumps(INVENTORY_PAYLOAD, indent=2)}
""".strip()


# ---------------------------------------------------------------------------
# ZERO PROMPT
# ---------------------------------------------------------------------------


def build_zero_prompt(
    case: BenchmarkCase,
    object_dna: ObjectDNAResponse,
) -> str:
    external_resources = list(
        case.external_resources
    )

    capability_graph = (
        build_compact_capability_graph(
            object_dna
        )
    )

    return f"""
You are ZERO's capability-bound physical planning layer.

You are NOT allowed to use an inventory object merely because you can
imagine a possible use for it.

Every physical use of an inventory object MUST be authorized by that
item's validated Object DNA.

For every inventory item participating in a plan step, cite one or more
exact Object DNA capabilities authorizing that use.

Explicit external resources are already available and do not require
inventory IDs or Object DNA capability citations.

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
          "purpose": "brief physical purpose"
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

- External resources may be used without inventory IDs.

- Never assign an inventory ID to an external resource.

- Every inventory item used in a step must cite at least one validated
  Object DNA capability.

- Every cited capability must exactly exist for that item.

- Do NOT invent capabilities.

- Do NOT infer a new physical use from object identity alone.

- Low-certainty capabilities are unavailable.

- Respect unknown_properties.

- Respect caution_notes.

- Do not convert an unknown property into an assumption merely because
  it makes the plan easier.

- Do not claim physical properties that the world model does not
  establish.

- Do not invent additional physical resources.

- Respect every constraint written in the goal.

- Maximum {MAX_PLAN_STEPS} steps.

- Keep each action concise: maximum about 25 words.

- Keep each capability purpose concise: maximum about 15 words.

- Keep each why_it_helps concise: maximum about 20 words.

- Do not repeat Object DNA descriptions in the plan.

- Return JSON only.


GOAL

{case.goal}


EXPLICIT EXTERNAL RESOURCES

{json.dumps(external_resources, indent=2)}


CANONICAL INVENTORY

{json.dumps(INVENTORY_PAYLOAD, indent=2)}


VALIDATED CAPABILITY GRAPH

{json.dumps(capability_graph, indent=2)}
""".strip()


# ---------------------------------------------------------------------------
# DETERMINISTIC VALIDATION FEEDBACK
# ---------------------------------------------------------------------------


def _validation_failure_to_critic(
    error: PlanValidationError,
) -> PlanCriticResult:
    """
    Convert a hard deterministic validation failure into repair feedback.

    This does not weaken or reinterpret the validator.
    It only communicates the exact failure back to the bounded repair model.
    """

    error_text = str(
        error
    )

    return PlanCriticResult(
        passed=False,
        findings=[
            PlanCriticFinding(
                step_order=None,

                claim=(
                    "Repaired plan failed deterministic "
                    "capability validation."
                ),

                issue_type=(
                    CriticIssueType.UNSUPPORTED_CAPABILITY
                ),

                severity=(
                    CriticSeverity.HIGH
                ),

                explanation=(
                    error_text
                ),

                recommended_fix=(
                    "Correct these exact deterministic "
                    "validator errors without inventing "
                    f"capabilities: {error_text}"
                ),
            )
        ],
    )


# ---------------------------------------------------------------------------
# RUN ONE BENCHMARK CASE
# ---------------------------------------------------------------------------


def run_benchmark_case(
    case: BenchmarkCase,
    *,
    object_dna: ObjectDNAResponse | None = None,
) -> CaseRunResult:
    """
    Run one baseline-vs-ZERO benchmark case.

    Human expectation/rationale metadata is not sent to either planner.
    """

    print()
    print(
        f"[{case.case_id}] "
        f"{case.name}"
    )

    # ------------------------------------------------------------------
    # BASELINE
    # ------------------------------------------------------------------

    print(
        f"[{case.case_id}] "
        "Running generic baseline..."
    )

    baseline_plan = call_planner(
        build_baseline_prompt(
            case
        )
    )

    baseline_plan = normalize_external_resource_ids(
        baseline_plan,
        case.external_resources,
    )

    baseline_plan = normalize_plan_item_ids(
        baseline_plan
    )

    validate_inventory_grounding(
        baseline_plan,
        VALID_ITEM_IDS,
    )

    # ------------------------------------------------------------------
    # WORLD MODEL
    # ------------------------------------------------------------------

    if object_dna is None:
        object_dna = (
            load_or_generate_object_dna()
        )

    # ------------------------------------------------------------------
    # INITIAL ZERO PLAN
    # ------------------------------------------------------------------

    print(
        f"[{case.case_id}] "
        "Running capability-bound ZERO planner..."
    )

    zero_plan = call_planner(
        build_zero_prompt(
            case,
            object_dna,
        )
    )

    zero_plan = normalize_external_resource_ids(
        zero_plan,
        case.external_resources,
    )

    zero_plan = normalize_plan_item_ids(
        zero_plan
    )

    print(
        f"[{case.case_id}] "
        "Running deterministic ZERO validation..."
    )

    zero_plan = validate_zero_plan(
        zero_plan,
        object_dna,
        VALID_ITEM_IDS,
    )

    print(
        f"[{case.case_id}] "
        "Running ZERO semantic critic..."
    )

    critic_result = audit_plan_semantics(
        plan=zero_plan,
        goal=case.goal,
        inventory=OBJECT_DNA_FIXTURE.items,
        object_dna=object_dna,
        external_resources=list(
            case.external_resources
        ),
    )

    zero_initial_plan = (
        zero_plan.model_copy(
            deep=True
        )
    )

    zero_initial_critic = (
        critic_result.model_copy(
            deep=True
        )
    )

    # ------------------------------------------------------------------
    # REPAIR STATE
    #
    # working_plan:
    #     candidate that the next repair should modify
    #
    # last_valid_plan:
    #     newest plan that passed deterministic validation
    #
    # last_semantic_critic:
    #     semantic audit corresponding to last_valid_plan
    #
    # repair_feedback:
    #     either semantic findings or deterministic validator findings
    # ------------------------------------------------------------------

    working_plan = zero_plan

    last_valid_plan = zero_plan

    last_semantic_critic = (
        critic_result
    )

    repair_feedback = (
        critic_result
    )

    repair_attempt = 0

    repair_validation_failures = 0

    # ------------------------------------------------------------------
    # BOUNDED ZERO REPAIR LOOP
    # ------------------------------------------------------------------

    while (
        not last_semantic_critic.passed
        and repair_attempt
        < MAX_REPAIR_ATTEMPTS
    ):
        repair_attempt += 1

        print(
            f"[{case.case_id}] "
            f"Repair attempt "
            f"{repair_attempt}/"
            f"{MAX_REPAIR_ATTEMPTS}..."
        )

        repaired_candidate = repair_plan(
            plan=working_plan,
            critic=repair_feedback,
            goal=case.goal,
            inventory=OBJECT_DNA_FIXTURE.items,
            object_dna=object_dna,
            external_resources=list(
                case.external_resources
            ),
        )

        repaired_candidate = (
            normalize_external_resource_ids(
                repaired_candidate,
                case.external_resources,
            )
        )

        repaired_candidate = (
            normalize_plan_item_ids(
                repaired_candidate
            )
        )

        print(
            f"[{case.case_id}] "
            "Revalidating repaired plan..."
        )

        try:
            repaired_candidate = (
                validate_zero_plan(
                    repaired_candidate,
                    object_dna,
                    VALID_ITEM_IDS,
                )
            )

        except PlanValidationError as exc:
            repair_validation_failures += 1

            print(
                f"[{case.case_id}] "
                f"Hard validator rejected repair "
                f"attempt {repair_attempt}:"
            )

            print(
                str(exc)
            )

            # Keep the invalid candidate only as the object
            # the next repair should fix.
            #
            # It never becomes the final ZERO plan unless it later
            # passes deterministic validation.
            working_plan = (
                repaired_candidate
            )

            repair_feedback = (
                _validation_failure_to_critic(
                    exc
                )
            )

            if (
                repair_attempt
                >= MAX_REPAIR_ATTEMPTS
            ):
                print(
                    f"[{case.case_id}] "
                    "No repair attempts remain; "
                    "discarding invalid candidate and "
                    "retaining last deterministic-valid plan."
                )

            else:
                print(
                    f"[{case.case_id}] "
                    "Next repair attempt will target "
                    "the deterministic validator errors."
                )

            continue

        # --------------------------------------------------------------
        # Only hard-valid candidates may reach semantic criticism.
        # --------------------------------------------------------------

        print(
            f"[{case.case_id}] "
            "Re-running semantic critic..."
        )

        repaired_critic = (
            audit_plan_semantics(
                plan=repaired_candidate,
                goal=case.goal,
                inventory=(
                    OBJECT_DNA_FIXTURE.items
                ),
                object_dna=object_dna,
                external_resources=list(
                    case.external_resources
                ),
            )
        )

        working_plan = (
            repaired_candidate
        )

        last_valid_plan = (
            repaired_candidate
        )

        last_semantic_critic = (
            repaired_critic
        )

        repair_feedback = (
            repaired_critic
        )

    # ------------------------------------------------------------------
    # FINAL ZERO STATE
    #
    # Important:
    # the final ZERO plan is ALWAYS the most recent plan that passed
    # deterministic validation.
    # ------------------------------------------------------------------

    zero_plan = (
        last_valid_plan
    )

    critic_result = (
        last_semantic_critic
    )

    # ------------------------------------------------------------------
    # NEUTRAL EVALUATION
    # ------------------------------------------------------------------

    print(
        f"[{case.case_id}] "
        "Running neutral baseline evaluation..."
    )

    baseline_evaluation = evaluate_plan(
        plan=baseline_plan,
        goal=case.goal,
        inventory=OBJECT_DNA_FIXTURE.items,
        object_dna=object_dna,
        external_resources=list(
            case.external_resources
        ),
    )

    print(
        f"[{case.case_id}] "
        "Running neutral ZERO evaluation..."
    )

    zero_evaluation = evaluate_plan(
        plan=zero_plan,
        goal=case.goal,
        inventory=OBJECT_DNA_FIXTURE.items,
        object_dna=object_dna,
        external_resources=list(
            case.external_resources
        ),
    )

    return CaseRunResult(
        case_id=case.case_id,
        case_name=case.name,
        expectation=case.expectation.value,

        baseline_plan=baseline_plan,

        zero_initial_plan=(
            zero_initial_plan
        ),

        zero_initial_critic=(
            zero_initial_critic
        ),

        zero_final_plan=(
            zero_plan
        ),

        zero_final_critic=(
            critic_result
        ),

        repair_attempts=(
            repair_attempt
        ),

        repair_validation_failures=(
            repair_validation_failures
        ),

        baseline_evaluation=(
            baseline_evaluation
        ),

        zero_evaluation=(
            zero_evaluation
        ),
    )