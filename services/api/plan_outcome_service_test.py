from experiment_runner import (
    load_or_generate_object_dna,
)
from object_dna_fixture import (
    OBJECT_DNA_FIXTURE,
)
from plan_outcome_schemas import (
    PlanOutcomeStatus,
)
from plan_outcome_service import (
    generate_plan_outcome,
)
from plan_validator import (
    validate_zero_plan,
)
from unseen_benchmark_cases import (
    get_unseen_benchmark_case,
)


case = get_unseen_benchmark_case(
    "U03"
)


print(
    "Loading frozen Object DNA..."
)

object_dna = (
    load_or_generate_object_dna()
)


print(
    "Generating outcome-aware ZERO response "
    "for frozen U03..."
)

outcome = generate_plan_outcome(
    goal=case.goal,
    inventory=OBJECT_DNA_FIXTURE.items,
    object_dna=object_dna,
    external_resources=case.external_resources,
)


print()
print("=" * 72)
print("U03 PLAN OUTCOME")
print("=" * 72)

print(
    outcome.model_dump_json(
        indent=2
    )
)


# ---------------------------------------------------------------------------
# U03 EXPECTATION
#
# The physical solution is known:
# use the spray bottle's dispense_liquid capability.
#
# Execution is blocked only by one concrete prerequisite:
# the unknown contents must first be identified as appropriate.
#
# Therefore this should be CONDITIONAL, not an empty PhysicalPlan.
# ---------------------------------------------------------------------------


assert (
    outcome.status
    == PlanOutcomeStatus.CONDITIONAL
), (
    "Frozen U03 should produce CONDITIONAL. "
    f"Got: {outcome.status.value}"
)


assert (
    outcome.plan
    is not None
), (
    "CONDITIONAL must contain the plan that becomes executable "
    "after requirements are satisfied."
)


assert outcome.requirements, (
    "U03 CONDITIONAL outcome must preserve the bottle-content "
    "verification requirement."
)


assert not outcome.blocking_reasons, (
    "U03 should use requirements rather than blocking_reasons."
)


# The actual bottle must participate in the future executable plan.
assert (
    "spray_bottles_01"
    in outcome.plan.item_ids_used
), (
    "U03 executable plan must use spray_bottles_01."
)


# ---------------------------------------------------------------------------
# HARD VALIDATION
#
# The conditional envelope does not weaken ZERO's existing physical
# validator. The plan that would execute after verification still has
# to pass exactly the same capability grounding rules.
# ---------------------------------------------------------------------------


valid_item_ids = {
    item.id
    for item in OBJECT_DNA_FIXTURE.items
}


validated_plan = validate_zero_plan(
    outcome.plan,
    object_dna,
    valid_item_ids,
)


assert validated_plan is not None


print()
print(
    "U03 OUTCOME STATUS:",
    outcome.status.value,
)

print(
    "U03 REQUIREMENTS:",
    len(outcome.requirements),
)

print(
    "U03 CONDITIONAL PLAN HARD VALIDATION: passed"
)

print()
print(
    "PLAN OUTCOME SERVICE TEST: passed"
)