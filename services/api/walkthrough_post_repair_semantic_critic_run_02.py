import argparse

import walkthrough_initial_semantic_repair_run_02 as repair2_run
import walkthrough_post_repair_semantic_critic_run as semantic_audit_run


DEFAULT_WALKTHROUGH_ID = repair2_run.DEFAULT_WALKTHROUGH_ID

FINAL_CACHE_PATH = (
    repair2_run
    .repair1_run
    .semantic_run
    .initial_plan_run
    .object_dna_run
    .PRIVATE_DIR
    / (
        f"{DEFAULT_WALKTHROUGH_ID}"
        "-semantic-critic-after-initial-semantic-repair-02.json"
    )
)


def configure_walkthrough_context(
    walkthrough_id: str,
) -> str:
    global FINAL_CACHE_PATH

    validated_id = (
        repair2_run
        .configure_walkthrough_context(
            walkthrough_id
        )
    )

    FINAL_CACHE_PATH = (
        repair2_run
        .repair1_run
        .semantic_run
        .initial_plan_run
        .object_dna_run
        .PRIVATE_DIR
        / (
            f"{validated_id}"
            "-semantic-critic-after-initial-semantic-repair-02.json"
        )
    )

    return validated_id


def load_final_repaired_plan_context(
    *,
    walkthrough_id: str,
    goal: str,
):
    """
    Reconstruct semantic-repair attempt 2 and deterministically
    revalidate it.

    No model calls occur here.
    """

    (
        initial_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        source_plan_sha256,
        _source_plan,
        source_repair_pipeline_sha256,
        semantic_pipeline_sha256,
        source_critic,
    ) = (
        repair2_run
        .load_semantic_failure_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    source_semantic_critic_sha256 = (
        repair2_run
        .repair1_run
        .sha256_payload(
            source_critic.model_dump(
                mode="json"
            )
        )
    )

    repair_pipeline_sha256 = (
        repair2_run
        .repair1_run
        .repair_pipeline_fingerprint()
    )

    repaired_plan = (
        repair2_run
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
            source_plan_sha256=(
                source_plan_sha256
            ),
            source_repair_pipeline_sha256=(
                source_repair_pipeline_sha256
            ),
            source_semantic_pipeline_sha256=(
                semantic_pipeline_sha256
            ),
            source_semantic_critic_sha256=(
                source_semantic_critic_sha256
            ),
            repair_pipeline_sha256=(
                repair_pipeline_sha256
            ),
        )
    )

    if repaired_plan is None:
        raise RuntimeError(
            "Matching semantic-repair attempt-2 cache "
            "was not found."
        )

    (
        validated_plan,
        validation_error,
    ) = (
        repair2_run
        .repair1_run
        .validate_repaired_plan(
            repaired_plan=(
                repaired_plan
            ),
            object_dna=(
                object_dna
            ),
            active_items=(
                active_items
            ),
            external_resources=(
                external_resources
            ),
        )
    )

    if validation_error is not None:
        raise RuntimeError(
            "Semantic-repair attempt 2 no longer passes "
            "deterministic validation: "
            f"{validation_error}"
        )

    repaired_plan_sha256 = (
        repair2_run
        .repair1_run
        .sha256_payload(
            validated_plan.model_dump(
                mode="json"
            )
        )
    )

    return (
        initial_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        source_semantic_critic_sha256,
        repair_pipeline_sha256,
        repaired_plan_sha256,
        validated_plan,
        semantic_pipeline_sha256,
    )


def print_critic(
    critic,
) -> None:
    print()
    print("=" * 72)

    print(
        "POST-REPAIR-2 SEMANTIC PHYSICAL AUDIT RESULT"
    )

    print("=" * 72)
    print()

    print(
        f"Passed: {critic.passed}"
    )

    print(
        f"Findings: {len(critic.findings)}"
    )

    if critic.findings:
        print()

        for index, finding in enumerate(
            critic.findings,
            start=1,
        ):
            print(
                f"{index}. severity: "
                f"{finding.severity.value}"
            )

            print(
                f"   issue type: "
                f"{finding.issue_type.value}"
            )

            print(
                f"   step order: "
                f"{finding.step_order}"
            )

            print(
                f"   claim: "
                f"{finding.claim}"
            )

            print(
                f"   explanation: "
                f"{finding.explanation}"
            )

            print(
                f"   recommended fix: "
                f"{finding.recommended_fix}"
            )

            print()

    if critic.passed:
        print(
            "Semantic repair attempt 2 passed "
            "the fresh semantic audit."
        )
    else:
        print(
            "Semantic repair attempt 2 still has "
            "blocking semantic findings."
        )

    print()

    print(
        "Repair budget is exhausted: 2 of 2."
    )

    print(
        "NO third repair attempt is permitted."
    )

    print()

    print(
        "Verification-gate processing has NOT been run yet."
    )

    print(
        "The pipeline-level final semantic recheck after "
        "verification-gate processing has NOT been run yet."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Fresh semantic audit after bounded semantic "
            "repair attempt 2 of 2. No repair path exists."
        )
    )

    parser.add_argument(
        "--walkthrough-id",
        default=(
            DEFAULT_WALKTHROUGH_ID
        ),
        help=(
            "Artifact namespace such as walkthrough-02."
        ),
    )

    parser.add_argument(
        "--goal",
        default=(
            repair2_run
            .repair1_run
            .semantic_run
            .initial_plan_run
            .DEFAULT_GOAL
        ),
        help=(
            "Goal whose final bounded repaired plan "
            "should be audited."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate repair-attempt-2 context and inspect "
            "audit-cache status without a model call."
        ),
    )

    parser.add_argument(
        "--max-new-audits",
        type=int,
        default=0,
        choices=[
            0,
            1,
        ],
        help=(
            "Maximum new semantic-audit invocations allowed. "
            "Normally one model call; malformed JSON may trigger "
            "one formatting-only repair call."
        ),
    )

    args = parser.parse_args()

    if (
        args.dry_run
        and
        args.max_new_audits != 0
    ):
        parser.error(
            "--dry-run cannot authorize a semantic audit."
        )

    goal = (
        args.goal.strip()
    )

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
        "ZERO POST-REPAIR-2 SEMANTIC CRITIC"
    )

    print("=" * 72)

    print(
        f"Walkthrough: {walkthrough_id}"
    )

    print(
        f"Goal: {goal}"
    )

    (
        initial_outcome,
        active_items,
        object_dna,
        external_resources,
        planning_input_sha256,
        semantic_context_sha256,
        source_semantic_critic_sha256,
        repair_pipeline_sha256,
        repaired_plan_sha256,
        validated_plan,
        semantic_pipeline_sha256,
    ) = (
        load_final_repaired_plan_context(
            walkthrough_id=(
                walkthrough_id
            ),
            goal=goal,
        )
    )

    #
    # IMPORTANT:
    #
    # load_final_repaired_plan_context() needs
    # semantic_audit_run.CACHE_PATH to remain pointed at
    # repair-attempt-1's audit while reconstructing the source
    # chain.
    #
    # Only after that source context has been fully loaded do
    # we redirect the shared cache helpers to repair attempt 2.
    #
    semantic_audit_run.CACHE_PATH = (
        FINAL_CACHE_PATH
    )

    cache_file_existed = (
        FINAL_CACHE_PATH.exists()
    )

    cached_critic = (
        semantic_audit_run
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
                source_semantic_critic_sha256
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

    if (
        cache_file_existed
        and
        cached_critic is None
    ):
        raise RuntimeError(
            "Existing post-repair-2 semantic cache is stale "
            "for the current inputs. Preserve and inspect it "
            "before authorizing another paid audit."
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
        f"Source semantic critic SHA-256: "
        f"{source_semantic_critic_sha256}"
    )

    print(
        f"Repair-2 pipeline SHA-256: "
        f"{repair_pipeline_sha256}"
    )

    print(
        f"Validated repair-2 plan SHA-256: "
        f"{repaired_plan_sha256}"
    )

    print(
        f"Semantic pipeline SHA-256: "
        f"{semantic_pipeline_sha256}"
    )

    print()

    print(
        f"Initial outcome status: "
        f"{initial_outcome.status.value}"
    )

    print(
        f"Conditional requirements: "
        f"{len(initial_outcome.requirements)}"
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
        f"Validated repair-2 plan steps: "
        f"{len(validated_plan.steps)}"
    )

    print()

    print(
        f"Post-repair-2 semantic cache: "
        f"{FINAL_CACHE_PATH.resolve()}"
    )

    if cached_critic is None:
        print(
            "Post-repair-2 semantic-critic cache: "
            "missing"
        )
    else:
        print(
            "Post-repair-2 semantic-critic cache: "
            "valid"
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
            "Repair budget remains exhausted: 2 of 2."
        )

        print(
            "NO repair path exists in this runner."
        )

        return

    if cached_critic is not None:
        print()

        print(
            "Reusing validated post-repair-2 "
            "semantic-critic cache."
        )

        print(
            "New semantic audit invocations: 0"
        )

        print_critic(
            cached_critic
        )

        return

    if (
        args.max_new_audits
        == 0
    ):
        print()

        print(
            "No paid semantic audit authorized "
            "(--max-new-audits is 0)."
        )

        return

    print()

    print(
        "Running ONE fresh semantic physical audit "
        "after repair attempt 2..."
    )

    print(
        "Normally 1 Nemotron call; malformed JSON may "
        "trigger one formatting-only repair call."
    )

    from plan_outcome_pipeline import (
        _build_execution_aware_goal,
    )

    from semantic_critic import (
        audit_plan_semantics,
    )

    execution_goal = (
        _build_execution_aware_goal(
            goal=goal,
            outcome=(
                initial_outcome
            ),
        )
    )

    critic = (
        audit_plan_semantics(
            plan=(
                validated_plan
            ),
            goal=(
                execution_goal
            ),
            inventory=(
                active_items
            ),
            object_dna=(
                object_dna
            ),
            external_resources=(
                external_resources
            ),
        )
    )

    semantic_audit_run.save_cache(
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
            source_semantic_critic_sha256
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
        critic=(
            critic
        ),
    )

    print()

    print(
        "Post-repair-2 semantic critic schema-valid "
        "and cached."
    )

    print(
        "New semantic audit invocations: 1"
    )

    print(
        "Saved private post-repair-2 semantic cache:"
    )

    print(
        FINAL_CACHE_PATH.resolve()
    )

    print_critic(
        critic
    )


if __name__ == "__main__":
    main()