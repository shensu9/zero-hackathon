from experiment_runner import (
    load_or_generate_object_dna,
)
from object_dna_fixture import (
    OBJECT_DNA_FIXTURE,
)
from plan_outcome_pipeline import (
    generate_safe_plan_outcome,
)
from plan_outcome_schemas import (
    PlanOutcomeStatus,
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
    "Running safe outcome pipeline "
    "for frozen U03..."
)

result = generate_safe_plan_outcome(
    goal=case.goal,
    inventory=OBJECT_DNA_FIXTURE.items,
    object_dna=object_dna,
    external_resources=(
        case.external_resources
    ),
)


outcome = result.outcome


print()
print("=" * 72)
print("SAFE U03 OUTCOME")
print("=" * 72)

print(
    outcome.model_dump_json(
        indent=2
    )
)


print()
print("=" * 72)
print("VERIFICATION GATE AUDIT")
print("=" * 72)

print(
    result
    .verification_gate_audit
    .model_dump_json(
        indent=2
    )
)


assert (
    outcome.status
    == PlanOutcomeStatus.CONDITIONAL
), (
    "U03 should remain CONDITIONAL."
)


assert outcome.plan is not None, (
    "U03 conditional outcome must contain "
    "a future executable plan."
)


assert outcome.requirements, (
    "U03 must preserve the verification "
    "requirement."
)


assert (
    result.verification_gate_audit.passed
), (
    "Safe pipeline must never return "
    "a failed verification gate."
)


assert (
    "spray_bottles_01"
    in outcome.plan.item_ids_used
), (
    "Future executable U03 plan must use "
    "spray_bottles_01."
)


print()
print(
    "U03 FINAL STATUS:",
    outcome.status.value,
)

print(
    "U03 GATE REPAIR ATTEMPTS:",
    result.gate_repair_attempts,
)

print(
    "U03 FINAL GATE AUDIT:",
    result.verification_gate_audit.passed,
)

print()
print(
    "SAFE PLAN OUTCOME PIPELINE TEST: passed"
)