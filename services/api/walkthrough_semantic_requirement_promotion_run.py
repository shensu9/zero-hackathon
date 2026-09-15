import argparse
import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, Field

import semantic_requirement_promotion as promotion
import walkthrough_post_repair_semantic_critic_run_02 as final_semantic_run

from plan_outcome_pipeline import (
    _replace_plan,
    _replace_requirements,
)
from plan_outcome_schemas import (
    PlanOutcome,
    PlanRequirement,
)


DEFAULT_WALKTHROUGH_ID = (
    final_semantic_run.DEFAULT_WALKTHROUGH_ID
)


CACHE_PATH = (
    final_semantic_run
    .repair2_run
    .repair1_run
    .semantic_run
    .initial_plan_run
    .object_dna_run
    .PRIVATE_DIR
    / (
        f"{DEFAULT_WALKTHROUGH_ID}"
        "-semantic-requirement-promotion-after-repair-02.json"
    )
)


class SemanticRequirementPromotionCache(
    BaseModel
):
    walkthrough_id: str = Field(
        min_length=1,
        max_length=128,
    )

    goal: str = Field(
        min_length=1,
        max_length=2000,
    )

    planning_input_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    semantic_context_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    repaired_plan_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    source_semantic_critic_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    semantic_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    promotion_pipeline_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    input_outcome_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )

    promoted_requirements: list[
        PlanRequirement
    ] = Field(
        min_length=1,
        max_length=5,
    )

    output_outcome: PlanOutcome


def configure_walkthrough_context(
    walkthrough_id: str,
) -> str:
    global CACHE_PATH

    validated_id = (
        final_semantic_run
        .configure_walkthrough_context(
            walkthrough_id
        )
    )

    CACHE_PATH = (
        final_semantic_run
        .repair2_run
        .repair1_run
        .semantic_run
        .initial_plan_run
        .object_dna_run
        .PRIVATE_DIR
        / (
            f"{validated_id}"
            "-semantic-requirement-promotion-after-repair-02.json"
        )
    )

    return validated_id


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


def promotion_pipeline_fingerprint() -> str:
    base = Path(__file__).resolve().parent

    filenames = (
        "semantic_requirement_promotion.py",
        "plan_outcome_schemas.py",
        "plan_outcome_pipeline.py",
    )

    payload = {}

    for filename in filenames:
        path = base / filename

        payload[filename] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

    return sha256_payload(
        payload
    )


def load_context(
    *,
    walkthrough_id: str,
    goal: str,
):
    (
        initial_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        _repair1_source_critic_sha256,
        repair_pipeline_sha256,
        repaired_plan_sha256,
        validated_plan,
        semantic_pipeline_sha256,
    ) = (
        final_semantic_run
        .load_final_repaired_plan_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    #
    # The context loader needs the repair-1 semantic cache while
    # reconstructing repair attempt 2. Only after that chain is
    # resolved do we point the shared audit helpers at the final
    # repair-2 semantic cache.
    #
    final_semantic_run.semantic_audit_run.CACHE_PATH = (
        final_semantic_run.FINAL_CACHE_PATH
    )

    critic = (
        final_semantic_run
        .semantic_audit_run
        .load_matching_cache(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
            planning_input_sha256=(
                planning_input_sha256
            ),
            semantic_context_sha256=(
                semantic_context_sha256
            ),
            source_semantic_critic_sha256=(
                _repair1_source_critic_sha256
            ),
            repair_pipeline_sha256=(
                repair_pipeline_sha256
            ),
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            semantic_pipeline_sha256=(
                semantic_pipeline_sha256
            ),
        )
    )

    if critic is None:
        raise RuntimeError(
            "Matching final post-repair-2 semantic critic "
            "cache was not found."
        )

    if critic.passed:
        raise RuntimeError(
            "Final post-repair-2 semantic critic already passes. "
            "Requirement promotion is not justified."
        )

    reason = (
        promotion
        .promotion_ineligibility_reason(
            outcome=(
                _replace_plan(
                    outcome=(
                        initial_outcome
                    ),
                    plan=(
                        validated_plan
                    ),
                )
            ),
            critic=critic,
        )
    )

    if reason is not None:
        raise RuntimeError(
            "Final semantic findings are not eligible for "
            "requirement promotion: "
            f"{reason}"
        )

    outcome_with_final_plan = (
        _replace_plan(
            outcome=(
                initial_outcome
            ),
            plan=(
                validated_plan
            ),
        )
    )

    input_outcome_sha256 = (
        sha256_payload(
            outcome_with_final_plan.model_dump(
                mode="json"
            )
        )
    )

    source_semantic_critic_sha256 = (
        sha256_payload(
            critic.model_dump(
                mode="json"
            )
        )
    )

    return (
        outcome_with_final_plan,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        repaired_plan_sha256,
        source_semantic_critic_sha256,
        semantic_pipeline_sha256,
        input_outcome_sha256,
        critic,
    )


def load_matching_cache(
    *,
    walkthrough_id: str,
    goal: str,
    planning_input_sha256: str,
    semantic_context_sha256: str,
    repaired_plan_sha256: str,
    source_semantic_critic_sha256: str,
    semantic_pipeline_sha256: str,
    promotion_pipeline_sha256: str,
    input_outcome_sha256: str,
):
    if not CACHE_PATH.exists():
        return None

    try:
        payload = json.loads(
            CACHE_PATH.read_text(
                encoding="utf-8"
            )
        )

        cache = (
            SemanticRequirementPromotionCache
            .model_validate(
                payload
            )
        )

    except Exception as exc:
        raise RuntimeError(
            "Existing semantic-requirement-promotion cache "
            "is invalid. Refusing another paid call until "
            f"inspected: {CACHE_PATH}"
        ) from exc

    checks = (
        (
            cache.walkthrough_id,
            walkthrough_id,
        ),
        (
            cache.goal,
            goal,
        ),
        (
            cache.planning_input_sha256,
            planning_input_sha256,
        ),
        (
            cache.semantic_context_sha256,
            semantic_context_sha256,
        ),
        (
            cache.repaired_plan_sha256,
            repaired_plan_sha256,
        ),
        (
            cache.source_semantic_critic_sha256,
            source_semantic_critic_sha256,
        ),
        (
            cache.semantic_pipeline_sha256,
            semantic_pipeline_sha256,
        ),
        (
            cache.promotion_pipeline_sha256,
            promotion_pipeline_sha256,
        ),
        (
            cache.input_outcome_sha256,
            input_outcome_sha256,
        ),
    )

    for actual, expected in checks:
        if actual != expected:
            raise RuntimeError(
                "Existing semantic-requirement-promotion cache "
                "is stale for the current inputs. Preserve and "
                "inspect it before authorizing another paid call."
            )

    return cache


def save_cache(
    *,
    walkthrough_id: str,
    goal: str,
    planning_input_sha256: str,
    semantic_context_sha256: str,
    repaired_plan_sha256: str,
    source_semantic_critic_sha256: str,
    semantic_pipeline_sha256: str,
    promotion_pipeline_sha256: str,
    input_outcome_sha256: str,
    promoted_requirements,
    output_outcome: PlanOutcome,
) -> None:
    cache = (
        SemanticRequirementPromotionCache(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
            planning_input_sha256=(
                planning_input_sha256
            ),
            semantic_context_sha256=(
                semantic_context_sha256
            ),
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            source_semantic_critic_sha256=(
                source_semantic_critic_sha256
            ),
            semantic_pipeline_sha256=(
                semantic_pipeline_sha256
            ),
            promotion_pipeline_sha256=(
                promotion_pipeline_sha256
            ),
            input_outcome_sha256=(
                input_outcome_sha256
            ),
            promoted_requirements=(
                promoted_requirements
            ),
            output_outcome=(
                output_outcome
            ),
        )
    )

    CACHE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = (
        CACHE_PATH.with_name(
            CACHE_PATH.name
            + ".tmp"
        )
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


def validate_output(
    *,
    input_outcome: PlanOutcome,
    cache: SemanticRequirementPromotionCache,
) -> None:
    output = cache.output_outcome

    if (
        output.status
        != input_outcome.status
    ):
        raise RuntimeError(
            "Requirement promotion changed PlanOutcome status."
        )

    if (
        output.plan
        != input_outcome.plan
    ):
        raise RuntimeError(
            "Requirement promotion modified the frozen PhysicalPlan."
        )

    existing_count = len(
        input_outcome.requirements
    )

    if (
        output.requirements[
            :existing_count
        ]
        != input_outcome.requirements
    ):
        raise RuntimeError(
            "Requirement promotion modified existing requirements."
        )

    if (
        output.requirements[
            existing_count:
        ]
        != cache.promoted_requirements
    ):
        raise RuntimeError(
            "Promoted requirements do not match output outcome."
        )

    if (
        len(output.requirements)
        > promotion.MAX_TOTAL_REQUIREMENTS
    ):
        raise RuntimeError(
            "Requirement promotion exceeded the outcome schema limit."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Bounded semantic requirement promotion after "
            "Walkthrough repair attempt 2."
        )
    )

    parser.add_argument(
        "--walkthrough-id",
        default=(
            DEFAULT_WALKTHROUGH_ID
        ),
    )

    parser.add_argument(
        "--goal",
        required=True,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    parser.add_argument(
        "--max-new-promotions",
        type=int,
        default=0,
        choices=[
            0,
            1,
        ],
    )

    args = parser.parse_args()

    if (
        args.dry_run
        and
        args.max_new_promotions != 0
    ):
        parser.error(
            "--dry-run cannot authorize a paid promotion call."
        )

    goal = args.goal.strip()

    if not goal:
        parser.error(
            "--goal may not be empty."
        )

    walkthrough_id = (
        configure_walkthrough_context(
            args.walkthrough_id
        )
    )

    print("=" * 72)
    print(
        "ZERO SEMANTIC REQUIREMENT PROMOTION - "
        "AFTER REPAIR 2"
    )
    print("=" * 72)

    print(
        f"Walkthrough: {walkthrough_id}"
    )

    print(
        f"Goal: {goal}"
    )

    (
        input_outcome,
        active_items,
        _object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        repaired_plan_sha256,
        source_semantic_critic_sha256,
        semantic_pipeline_sha256,
        input_outcome_sha256,
        critic,
    ) = (
        load_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    promotion_pipeline_sha256 = (
        promotion_pipeline_fingerprint()
    )

    cached = (
        load_matching_cache(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
            planning_input_sha256=(
                planning_input_sha256
            ),
            semantic_context_sha256=(
                semantic_context_sha256
            ),
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            source_semantic_critic_sha256=(
                source_semantic_critic_sha256
            ),
            semantic_pipeline_sha256=(
                semantic_pipeline_sha256
            ),
            promotion_pipeline_sha256=(
                promotion_pipeline_sha256
            ),
            input_outcome_sha256=(
                input_outcome_sha256
            ),
        )
    )

    print()

    print(
        f"Planning input SHA-256: "
        f"{planning_input_sha256}"
    )

    print(
        f"Semantic execution-context SHA-256: "
        f"{semantic_context_sha256}"
    )

    print(
        f"Final repaired-plan SHA-256: "
        f"{repaired_plan_sha256}"
    )

    print(
        f"Source final semantic critic SHA-256: "
        f"{source_semantic_critic_sha256}"
    )

    print(
        f"Semantic pipeline SHA-256: "
        f"{semantic_pipeline_sha256}"
    )

    print(
        f"Promotion pipeline SHA-256: "
        f"{promotion_pipeline_sha256}"
    )

    print(
        f"Input outcome SHA-256: "
        f"{input_outcome_sha256}"
    )

    print()

    print(
        f"Outcome status: "
        f"{input_outcome.status.value}"
    )

    print(
        f"Existing requirements: "
        f"{len(input_outcome.requirements)}"
    )

    print(
        f"Blocking semantic findings: "
        f"{len(critic.findings)}"
    )

    print(
        f"Active inventory items: "
        f"{len(active_items)}"
    )

    print(
        f"External resources: "
        f"{external_resources}"
    )

    print()

    print(
        f"Promotion cache: "
        f"{CACHE_PATH.resolve()}"
    )

    if cached is None:
        print(
            "Semantic requirement promotion cache: missing"
        )
    else:
        print(
            "Semantic requirement promotion cache: valid"
        )

    if args.dry_run:
        print()

        print(
            "DRY RUN COMPLETE - NO MODEL CALL MADE"
        )

        print(
            "Model calls: 0"
        )

        print(
            "PhysicalPlan repair budget remains exhausted: 2 of 2."
        )

        print(
            "Maximum future promotion calls from this runner: 1."
        )

        return

    if cached is None:
        if (
            args.max_new_promotions
            == 0
        ):
            print()

            print(
                "No paid requirement promotion authorized "
                "(--max-new-promotions is 0)."
            )

            return

        print()

        print(
            "Running ONE semantic requirement promotion call..."
        )

        print(
            "PhysicalPlan remains frozen. "
            "No third plan repair is permitted."
        )

        promoted_requirements = (
            promotion
            .promote_semantic_findings_to_requirements(
                outcome=(
                    input_outcome
                ),
                critic=critic,
                goal=goal,
                inventory=(
                    active_items
                ),
                external_resources=(
                    external_resources
                ),
            )
        )

        output_outcome = (
            _replace_requirements(
                outcome=(
                    input_outcome
                ),
                requirements=[
                    *input_outcome.requirements,
                    *promoted_requirements,
                ],
            )
        )

        save_cache(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
            planning_input_sha256=(
                planning_input_sha256
            ),
            semantic_context_sha256=(
                semantic_context_sha256
            ),
            repaired_plan_sha256=(
                repaired_plan_sha256
            ),
            source_semantic_critic_sha256=(
                source_semantic_critic_sha256
            ),
            semantic_pipeline_sha256=(
                semantic_pipeline_sha256
            ),
            promotion_pipeline_sha256=(
                promotion_pipeline_sha256
            ),
            input_outcome_sha256=(
                input_outcome_sha256
            ),
            promoted_requirements=(
                promoted_requirements
            ),
            output_outcome=(
                output_outcome
            ),
        )

        cached = (
            SemanticRequirementPromotionCache(
                walkthrough_id=(
                    walkthrough_id
                ),
                goal=goal,
                planning_input_sha256=(
                    planning_input_sha256
                ),
                semantic_context_sha256=(
                    semantic_context_sha256
                ),
                repaired_plan_sha256=(
                    repaired_plan_sha256
                ),
                source_semantic_critic_sha256=(
                    source_semantic_critic_sha256
                ),
                semantic_pipeline_sha256=(
                    semantic_pipeline_sha256
                ),
                promotion_pipeline_sha256=(
                    promotion_pipeline_sha256
                ),
                input_outcome_sha256=(
                    input_outcome_sha256
                ),
                promoted_requirements=(
                    promoted_requirements
                ),
                output_outcome=(
                    output_outcome
                ),
            )
        )

        print()

        print(
            "Promotion result schema-valid and cached."
        )

        print(
            "New semantic requirement promotion calls: 1"
        )

        print(
            "Saved private promotion cache:"
        )

        print(
            CACHE_PATH.resolve()
        )

    else:
        print()

        print(
            "Reusing validated semantic requirement "
            "promotion cache."
        )

        print(
            "New semantic requirement promotion calls: 0"
        )

    validate_output(
        input_outcome=(
            input_outcome
        ),
        cache=cached,
    )

    print()
    print("=" * 72)
    print(
        "PROMOTION RESULT"
    )
    print("=" * 72)

    print()

    print(
        f"Promoted requirements: "
        f"{len(cached.promoted_requirements)}"
    )

    for index, requirement in enumerate(
        cached.promoted_requirements,
        start=1,
    ):
        print()

        print(
            f"{index}. requirement: "
            f"{requirement.requirement}"
        )

        print(
            f"   how_to_verify: "
            f"{requirement.how_to_verify}"
        )

        print(
            f"   if_not_met: "
            f"{requirement.if_not_met}"
        )

    print()

    print(
        f"Total requirements after promotion: "
        f"{len(cached.output_outcome.requirements)}"
    )

    print(
        "Frozen PhysicalPlan unchanged: YES"
    )

    print(
        "PhysicalPlan repair budget: 2 of 2 exhausted."
    )

    print()

    print(
        "Verification-gate auditing and final semantic "
        "recheck have NOT been run yet."
    )


if __name__ == "__main__":
    main()