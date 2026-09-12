import re
import unicodedata

from critic_schemas import (
    CriticSeverity,
    PlanCriticFinding,
    PlanCriticResult,
)
from plan_schemas import (
    PhysicalPlan,
)
from semantic_critic import (
    _build_semantic_field_map,
)


def _normalize_text(
    value: str,
) -> str:
    """
    Normalize text only for conservative claim-persistence matching.

    Do not perform semantic rewriting here.
    """

    value = unicodedata.normalize(
        "NFKC",
        value,
    )

    value = value.casefold()

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def _field_scope(
    *,
    field_map: dict[str, str],
    finding: PlanCriticFinding,
) -> dict[str, str]:
    """
    Restrict matching to the critic's declared scope.

    Step finding:
        only fields belonging to that step.

    Plan-level finding:
        title, summary, assumptions, risks, constraints.

    This makes the guard deliberately conservative.
    """

    if finding.step_order is not None:
        prefix = (
            f"step:{finding.step_order}:"
        )

        return {
            field_id: text
            for field_id, text
            in field_map.items()
            if field_id.startswith(
                prefix
            )
        }

    return {
        field_id: text
        for field_id, text
        in field_map.items()
        if not field_id.startswith(
            "step:"
        )
    }


def _claim_matches(
    *,
    claim: str,
    fields: dict[str, str],
) -> list[str]:
    """
    Return fields containing the critic claim as a normalized literal phrase.

    This is intentionally NOT fuzzy or semantic matching.
    """

    normalized_claim = (
        _normalize_text(
            claim
        )
    )

    if not normalized_claim:
        return []

    return [
        field_id
        for field_id, field_text
        in fields.items()
        if normalized_claim
        in _normalize_text(
            field_text
        )
    ]


def find_persisted_critic_findings(
    *,
    before_plan: PhysicalPlan,
    repaired_plan: PhysicalPlan,
    critic: PlanCriticResult,
) -> PlanCriticResult | None:
    """
    Detect critic claims that definitely survived a repair.

    This is a ONE-WAY guard.

    If it returns findings:
        the repair definitely failed to close those findings.

    If it returns None:
        the repair is NOT proven safe.
        Normal deterministic + semantic validation must still run.

    A claim is considered deterministically persisted only when:

    1. it is MEDIUM/HIGH,
    2. its normalized literal phrase occurs in exactly one field in the
       critic's scope BEFORE repair, and
    3. the same normalized literal phrase still occurs somewhere in the
       same scope AFTER repair.

    Requiring a unique pre-repair source keeps this check conservative.
    """

    before_map = (
        _build_semantic_field_map(
            before_plan
        )
    )

    repaired_map = (
        _build_semantic_field_map(
            repaired_plan
        )
    )

    persisted: list[
        PlanCriticFinding
    ] = []

    for finding in critic.findings:
        if finding.severity not in {
            CriticSeverity.MEDIUM,
            CriticSeverity.HIGH,
        }:
            continue

        before_scope = _field_scope(
            field_map=before_map,
            finding=finding,
        )

        repaired_scope = _field_scope(
            field_map=repaired_map,
            finding=finding,
        )

        before_matches = _claim_matches(
            claim=finding.claim,
            fields=before_scope,
        )

        # We only make a deterministic conclusion when the rejected
        # phrase has one unambiguous source in the pre-repair plan.
        if len(before_matches) != 1:
            continue

        repaired_matches = _claim_matches(
            claim=finding.claim,
            fields=repaired_scope,
        )

        if repaired_matches:
            persisted.append(
                finding
            )

    if not persisted:
        return None

    return PlanCriticResult(
        passed=False,
        findings=persisted,
    )