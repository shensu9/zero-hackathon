import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel, Field

import semantic_critic
from critic_schemas import PlanCriticResult
from plan_outcome_pipeline import _audit_outcome_plan
from walkthrough_final_semantic_critic_run import (
    CACHE_PATH as STANDARD_FINAL_CACHE_PATH,
    load_matching_cache as load_standard_final_cache,
    load_post_gate_context,
    print_critic,
)
from walkthrough_goal_relevance_run import GOAL
from walkthrough_semantic_critic_run import (
    semantic_pipeline_fingerprint,
)


CACHE_PATH = Path(
    "sample_data/private/"
    "walkthrough-01-final-semantic-critic-truncation-retry-01.json"
)

ORIGINAL_MAIN_MAX_TOKENS = 4500
RETRY_MAIN_MAX_TOKENS = 8000

RETRY_POLICY_VERSION = (
    "final-semantic-truncation-retry-v1"
)


class FinalSemanticRetryCache(BaseModel):
    """
    Cache for ONE transport-level retry of the final semantic audit.

    This is NOT another plan-repair attempt.

    The semantic prompt, model, parser, inventory, Object DNA, goal, and
    post-gate outcome remain unchanged. Only the main critic completion
    token ceiling is increased because the previous response ended with
    finish_reason='length'.
    """

    goal: str = Field(
        min_length=1,
        max_length=2000,
    )

    planning_input_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    gate_output_outcome_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    semantic_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    retry_execution_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    original_main_max_tokens: int = Field(
        ge=1,
    )

    retry_main_max_tokens: int = Field(
        ge=1,
    )

    critic: PlanCriticResult


def canonical_json(
    payload,
) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_payload(
    payload,
) -> str:
    return hashlib.sha256(
        canonical_json(
            payload
        ).encode("utf-8")
    ).hexdigest()


def retry_execution_fingerprint(
    *,
    semantic_pipeline_sha256: str,
) -> str:
    """
    Bind the exceptional retry cache to:
    - the exact unchanged semantic pipeline
    - this exact retry-runner implementation
    - the model
    - the original/retry token ceilings
    - the retry-policy version
    """

    digest = hashlib.sha256()

    digest.update(
        RETRY_POLICY_VERSION.encode(
            "utf-8"
        )
    )

    digest.update(
        b"\0"
    )

    digest.update(
        semantic_pipeline_sha256.encode(
            "utf-8"
        )
    )

    digest.update(
        b"\0"
    )

    digest.update(
        semantic_critic.MODEL.encode(
            "utf-8"
        )
    )

    digest.update(
        b"\0"
    )

    digest.update(
        str(
            ORIGINAL_MAIN_MAX_TOKENS
        ).encode("utf-8")
    )

    digest.update(
        b"\0"
    )

    digest.update(
        str(
            RETRY_MAIN_MAX_TOKENS
        ).encode("utf-8")
    )

    digest.update(
        b"\0"
    )

    digest.update(
        Path(__file__).read_bytes()
    )

    return digest.hexdigest()


def load_matching_retry_cache(
    *,
    planning_input_sha256: str,
    gate_output_outcome_sha256: str,
    semantic_pipeline_sha256: str,
    retry_execution_sha256: str,
) -> PlanCriticResult | None:
    if not CACHE_PATH.exists():
        return None

    try:
        payload = json.loads(
            CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        cache = (
            FinalSemanticRetryCache.model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing final semantic truncation-retry cache "
            "is invalid. Refusing to overwrite it until inspected: "
            f"{CACHE_PATH}"
        ) from exc

    if cache.goal != GOAL:
        return None

    if (
        cache.planning_input_sha256
        != planning_input_sha256
    ):
        return None

    if (
        cache.gate_output_outcome_sha256
        != gate_output_outcome_sha256
    ):
        return None

    if (
        cache.semantic_pipeline_sha256
        != semantic_pipeline_sha256
    ):
        return None

    if (
        cache.retry_execution_sha256
        != retry_execution_sha256
    ):
        return None

    if (
        cache.original_main_max_tokens
        != ORIGINAL_MAIN_MAX_TOKENS
    ):
        return None

    if (
        cache.retry_main_max_tokens
        != RETRY_MAIN_MAX_TOKENS
    ):
        return None

    return cache.critic


def save_retry_cache(
    *,
    planning_input_sha256: str,
    gate_output_outcome_sha256: str,
    semantic_pipeline_sha256: str,
    retry_execution_sha256: str,
    critic: PlanCriticResult,
) -> None:
    cache = FinalSemanticRetryCache(
        goal=GOAL,
        planning_input_sha256=planning_input_sha256,
        gate_output_outcome_sha256=gate_output_outcome_sha256,
        semantic_pipeline_sha256=semantic_pipeline_sha256,
        retry_execution_sha256=retry_execution_sha256,
        original_main_max_tokens=ORIGINAL_MAIN_MAX_TOKENS,
        retry_main_max_tokens=RETRY_MAIN_MAX_TOKENS,
        critic=critic,
    )

    CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = CACHE_PATH.with_name(
        CACHE_PATH.name + ".tmp"
    )

    temporary_path.write_text(
        cache.model_dump_json(
            indent=2
        ),
        encoding="utf-8",
    )

    temporary_path.replace(
        CACHE_PATH
    )


def run_truncation_retry(
    *,
    outcome,
    active_items,
    object_dna,
    external_resources,
):
    """
    Execute the exact existing production semantic audit while overriding
    ONLY the main audit's max_tokens=4500 request to 8000.

    The semantic_critic.py source file is not modified.

    If semantic_critic.py makes its optional malformed-JSON formatting
    repair call with max_tokens=2500, that request is left unchanged.
    """

    original_create = (
        semantic_critic.client.chat.completions.create
    )

    call_count = 0
    main_budget_override_count = 0

    def create_with_extended_main_budget(
        *args,
        **kwargs,
    ):
        nonlocal call_count
        nonlocal main_budget_override_count

        call_count += 1

        forwarded_kwargs = dict(
            kwargs
        )

        if (
            forwarded_kwargs.get(
                "max_tokens"
            )
            == ORIGINAL_MAIN_MAX_TOKENS
        ):
            forwarded_kwargs[
                "max_tokens"
            ] = RETRY_MAIN_MAX_TOKENS

            main_budget_override_count += 1

        return original_create(
            *args,
            **forwarded_kwargs,
        )

    with patch.object(
        semantic_critic.client.chat.completions,
        "create",
        side_effect=create_with_extended_main_budget,
    ):
        critic = _audit_outcome_plan(
            outcome=outcome,
            goal=GOAL,
            inventory=active_items,
            object_dna=object_dna,
            external_resources=external_resources,
        )

    if main_budget_override_count != 1:
        raise RuntimeError(
            "Expected exactly one 4500->8000 main semantic-audit "
            "token-budget override, but observed "
            f"{main_budget_override_count}."
        )

    return (
        critic,
        call_count,
        main_budget_override_count,
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate the exact post-gate context and retry-cache "
            "state without making a model call."
        ),
    )

    parser.add_argument(
        "--max-new-retries",
        type=int,
        default=0,
        choices=[0, 1],
        help=(
            "Maximum new truncation-retry audit invocations allowed. "
            "Only 0 or 1 is valid. Default 0."
        ),
    )

    args = parser.parse_args()

    if (
        args.dry_run
        and args.max_new_retries != 0
    ):
        parser.error(
            "--dry-run cannot authorize a paid retry."
        )

    print("=" * 72)
    print("ZERO FINAL SEMANTIC AUDIT — TRUNCATION RETRY 1")
    print("=" * 72)

    (
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        gate_output_outcome_sha256,
        outcome,
    ) = load_post_gate_context()

    semantic_sha256 = (
        semantic_pipeline_fingerprint()
    )

    standard_cached_critic = (
        load_standard_final_cache(
            planning_input_sha256=planning_input_sha256,
            gate_output_outcome_sha256=gate_output_outcome_sha256,
            semantic_pipeline_sha256=semantic_sha256,
        )
    )

    if standard_cached_critic is not None:
        print()
        print(
            "A valid standard final semantic cache already exists."
        )

        print(
            "Truncation retry is not justified."
        )

        print_critic(
            standard_cached_critic
        )

        return

    retry_sha256 = (
        retry_execution_fingerprint(
            semantic_pipeline_sha256=semantic_sha256,
        )
    )

    cached_retry = (
        load_matching_retry_cache(
            planning_input_sha256=planning_input_sha256,
            gate_output_outcome_sha256=gate_output_outcome_sha256,
            semantic_pipeline_sha256=semantic_sha256,
            retry_execution_sha256=retry_sha256,
        )
    )

    print()
    print(
        f"Outcome status: "
        f"{outcome.status.value}"
    )

    print(
        f"Plan title: "
        f"{outcome.plan.title}"
    )

    print(
        f"Plan steps: "
        f"{len(outcome.plan.steps)}"
    )

    print(
        f"Active inventory items: "
        f"{len(active_items)}"
    )

    print(
        f"Object DNA items: "
        f"{len(object_dna.objects)}"
    )

    print(
        f"External resources: "
        f"{external_resources}"
    )

    print(
        f"Planning input SHA-256: "
        f"{planning_input_sha256}"
    )

    print(
        f"Post-gate outcome SHA-256: "
        f"{gate_output_outcome_sha256}"
    )

    print(
        f"Semantic pipeline SHA-256: "
        f"{semantic_sha256}"
    )

    print(
        f"Retry execution SHA-256: "
        f"{retry_sha256}"
    )

    print(
        f"Main critic token budget: "
        f"{ORIGINAL_MAIN_MAX_TOKENS} -> "
        f"{RETRY_MAIN_MAX_TOKENS}"
    )

    print()

    if STANDARD_FINAL_CACHE_PATH.exists():
        print(
            "Standard final semantic cache file exists, "
            "but it did not validate for the current context."
        )
    else:
        print(
            "Standard final semantic cache: absent"
        )

    if cached_retry is None:
        print(
            "Truncation-retry cache: missing/stale"
        )

    else:
        print(
            "Truncation-retry cache: valid"
        )

    if args.dry_run:
        print()
        print(
            "DRY RUN COMPLETE — NO MODEL CALL MADE"
        )

        print(
            "This retry changes only the main completion token ceiling."
        )

        print(
            "Plan-repair budget remains exhausted at 2 of 2."
        )

        if cached_retry is not None:
            print_critic(
                cached_retry
            )

        return

    if cached_retry is not None:
        print()
        print(
            "Reusing validated truncation-retry cache."
        )

        print(
            "New model calls: 0"
        )

        print_critic(
            cached_retry
        )

        return

    if args.max_new_retries == 0:
        print()
        print(
            "No paid truncation retry authorized "
            "(--max-new-retries is 0)."
        )

        return

    print()
    print(
        "Running ONE final semantic audit transport retry..."
    )

    print(
        "Same semantic pipeline; only main max_tokens increases "
        f"from {ORIGINAL_MAIN_MAX_TOKENS} to "
        f"{RETRY_MAIN_MAX_TOKENS}."
    )

    print(
        "No plan repair is permitted."
    )

    (
        critic,
        model_call_count,
        main_budget_override_count,
    ) = run_truncation_retry(
        outcome=outcome,
        active_items=active_items,
        object_dna=object_dna,
        external_resources=external_resources,
    )

    save_retry_cache(
        planning_input_sha256=planning_input_sha256,
        gate_output_outcome_sha256=gate_output_outcome_sha256,
        semantic_pipeline_sha256=semantic_sha256,
        retry_execution_sha256=retry_sha256,
        critic=critic,
    )

    print()
    print(
        "Final semantic truncation-retry result "
        "schema-valid and cached."
    )

    print(
        f"Model calls during retry invocation: "
        f"{model_call_count}"
    )

    print(
        f"Main budget overrides applied: "
        f"{main_budget_override_count}"
    )

    print(
        "Saved private retry cache:"
    )

    print(
        CACHE_PATH.resolve()
    )

    print_critic(
        critic
    )


if __name__ == "__main__":
    main()