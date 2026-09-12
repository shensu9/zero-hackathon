import json

from critic_schemas import (
    PlanCriticFinding,
)
from plan_schemas import (
    CapabilityUse,
    PhysicalPlan,
    PlanStep,
)
from semantic_critic import (
    IncompleteSemanticCoverageError,
    SemanticAuditEnvelope,
    _build_semantic_critic_prompt,
    _build_semantic_field_map,
    _parse_critic_output,
    _validate_semantic_coverage,
)


def build_plan() -> PhysicalPlan:
    return PhysicalPlan(
        title="Zero-Cost Product Photography Setup",
        summary=(
            "Use a blanket backdrop and desk surface "
            "for product photography."
        ),
        item_ids_used=[
            "blanket_01",
            "desk_01",
        ],
        steps=[
            PlanStep(
                order=1,
                action=(
                    "Hang the blanket as a backdrop."
                ),
                item_ids=[
                    "blanket_01",
                ],
                capability_uses=[
                    CapabilityUse(
                        item_id="blanket_01",
                        capability="hang",
                        purpose=(
                            "Hang blanket as backdrop."
                        ),
                    ),
                ],
                why_it_helps=(
                    "Provides a uniform background."
                ),
            ),
            PlanStep(
                order=2,
                action=(
                    "Place the product on the desk."
                ),
                item_ids=[
                    "desk_01",
                ],
                capability_uses=[
                    CapabilityUse(
                        item_id="desk_01",
                        capability="provide_surface",
                        purpose=(
                            "Provide surface for product."
                        ),
                    ),
                ],
                why_it_helps=(
                    "Offers a flat area for the product."
                ),
            ),
        ],
        assumptions=[
            (
                "Product fits comfortably on the desk."
            ),
        ],
        unresolved_risks=[
            (
                "Blanket may move during use."
            ),
        ],
        constraint_check=[
            (
                "Budget remains $0."
            ),
        ],
    )


def build_finding(
    *,
    claim: str = "Provides a uniform background",
    severity: str = "medium",
) -> PlanCriticFinding:
    return PlanCriticFinding(
        step_order=1,
        claim=claim,
        issue_type=(
            "unsupported_physical_claim"
        ),
        severity=severity,
        explanation=(
            "Uniform appearance is not established "
            "by the blanket capabilities."
        ),
        recommended_fix=(
            "Remove the uniformity claim."
        ),
    )


def test_field_map_is_exact_and_complete():
    field_map = _build_semantic_field_map(
        build_plan()
    )

    expected_keys = [
        "title",
        "summary",
        "step:1:action",
        "step:1:capability:1:purpose",
        "step:1:why_it_helps",
        "step:2:action",
        "step:2:capability:1:purpose",
        "step:2:why_it_helps",
        "assumption:1",
        "risk:1",
        "constraint:1",
    ]

    assert list(
        field_map.keys()
    ) == expected_keys

    assert field_map[
        "step:1:why_it_helps"
    ] == (
        "Provides a uniform background."
    )

    assert field_map[
        "assumption:1"
    ] == (
        "Product fits comfortably on the desk."
    )


def test_valid_exact_coverage_passes():
    field_ids = list(
        _build_semantic_field_map(
            build_plan()
        ).keys()
    )

    coverage = {
        field_id: []
        for field_id in field_ids
    }

    coverage[
        "step:1:why_it_helps"
    ] = [1]

    envelope = SemanticAuditEnvelope(
        findings=[
            build_finding()
        ],
        coverage=coverage,
    )

    _validate_semantic_coverage(
        envelope=envelope,
        required_field_ids=field_ids,
    )


def test_missing_field_is_rejected():
    field_ids = list(
        _build_semantic_field_map(
            build_plan()
        ).keys()
    )

    coverage = {
        field_id: []
        for field_id in field_ids
    }

    del coverage[
        "step:1:why_it_helps"
    ]

    envelope = SemanticAuditEnvelope(
        findings=[],
        coverage=coverage,
    )

    try:
        _validate_semantic_coverage(
            envelope=envelope,
            required_field_ids=field_ids,
        )

    except IncompleteSemanticCoverageError:
        return

    raise AssertionError(
        "Missing semantic field was accepted."
    )


def test_unknown_extra_field_is_rejected():
    field_ids = list(
        _build_semantic_field_map(
            build_plan()
        ).keys()
    )

    coverage = {
        field_id: []
        for field_id in field_ids
    }

    coverage[
        "step:99:why_it_helps"
    ] = []

    envelope = SemanticAuditEnvelope(
        findings=[],
        coverage=coverage,
    )

    try:
        _validate_semantic_coverage(
            envelope=envelope,
            required_field_ids=field_ids,
        )

    except IncompleteSemanticCoverageError:
        return

    raise AssertionError(
        "Unknown semantic field was accepted."
    )


def test_invalid_finding_reference_is_rejected():
    field_ids = list(
        _build_semantic_field_map(
            build_plan()
        ).keys()
    )

    coverage = {
        field_id: []
        for field_id in field_ids
    }

    coverage[
        "step:1:why_it_helps"
    ] = [2]

    envelope = SemanticAuditEnvelope(
        findings=[
            build_finding()
        ],
        coverage=coverage,
    )

    try:
        _validate_semantic_coverage(
            envelope=envelope,
            required_field_ids=field_ids,
        )

    except IncompleteSemanticCoverageError:
        return

    raise AssertionError(
        "Reference to nonexistent finding was accepted."
    )


def test_zero_finding_reference_is_rejected():
    field_ids = list(
        _build_semantic_field_map(
            build_plan()
        ).keys()
    )

    coverage = {
        field_id: []
        for field_id in field_ids
    }

    coverage[
        "step:1:why_it_helps"
    ] = [0]

    envelope = SemanticAuditEnvelope(
        findings=[
            build_finding()
        ],
        coverage=coverage,
    )

    try:
        _validate_semantic_coverage(
            envelope=envelope,
            required_field_ids=field_ids,
        )

    except IncompleteSemanticCoverageError:
        return

    raise AssertionError(
        "Finding reference 0 was accepted."
    )


def test_duplicate_reference_is_rejected():
    field_ids = list(
        _build_semantic_field_map(
            build_plan()
        ).keys()
    )

    coverage = {
        field_id: []
        for field_id in field_ids
    }

    coverage[
        "step:1:why_it_helps"
    ] = [
        1,
        1,
    ]

    envelope = SemanticAuditEnvelope(
        findings=[
            build_finding()
        ],
        coverage=coverage,
    )

    try:
        _validate_semantic_coverage(
            envelope=envelope,
            required_field_ids=field_ids,
        )

    except IncompleteSemanticCoverageError:
        return

    raise AssertionError(
        "Duplicate finding reference was accepted."
    )


def test_unattached_finding_is_rejected():
    field_ids = list(
        _build_semantic_field_map(
            build_plan()
        ).keys()
    )

    coverage = {
        field_id: []
        for field_id in field_ids
    }

    envelope = SemanticAuditEnvelope(
        findings=[
            build_finding()
        ],
        coverage=coverage,
    )

    try:
        _validate_semantic_coverage(
            envelope=envelope,
            required_field_ids=field_ids,
        )

    except IncompleteSemanticCoverageError:
        return

    raise AssertionError(
        "Unattached semantic finding was accepted."
    )


def test_no_findings_with_full_coverage_passes():
    field_ids = list(
        _build_semantic_field_map(
            build_plan()
        ).keys()
    )

    envelope = SemanticAuditEnvelope(
        findings=[],
        coverage={
            field_id: []
            for field_id in field_ids
        },
    )

    _validate_semantic_coverage(
        envelope=envelope,
        required_field_ids=field_ids,
    )


def test_parse_derives_failed_result_from_medium_finding():
    field_ids = list(
        _build_semantic_field_map(
            build_plan()
        ).keys()
    )

    coverage = {
        field_id: []
        for field_id in field_ids
    }

    coverage[
        "step:1:why_it_helps"
    ] = [1]

    payload = {
        "findings": [
            build_finding().model_dump(
                mode="json"
            )
        ],
        "coverage": coverage,
    }

    result = _parse_critic_output(
        raw_output=json.dumps(
            payload
        ),
        required_field_ids=field_ids,
    )

    assert result.passed is False
    assert len(
        result.findings
    ) == 1


def test_parse_derives_pass_from_low_only_finding():
    field_ids = list(
        _build_semantic_field_map(
            build_plan()
        ).keys()
    )

    coverage = {
        field_id: []
        for field_id in field_ids
    }

    coverage[
        "step:1:why_it_helps"
    ] = [1]

    payload = {
        "findings": [
            build_finding(
                severity="low"
            ).model_dump(
                mode="json"
            )
        ],
        "coverage": coverage,
    }

    result = _parse_critic_output(
        raw_output=json.dumps(
            payload
        ),
        required_field_ids=field_ids,
    )

    assert result.passed is True
    assert len(
        result.findings
    ) == 1


def test_prompt_contains_exact_coverage_contract():
    plan = build_plan()

    field_map = (
        _build_semantic_field_map(
            plan
        )
    )

    prompt = (
        _build_semantic_critic_prompt(
            plan=plan,
            goal=(
                "Create a $0 product photography "
                "setup using existing resources."
            ),
            inventory_payload=[
                {
                    "id":
                        "blanket_01",

                    "name":
                        "blanket",

                    "description":
                        "Large blanket.",
                },
                {
                    "id":
                        "desk_01",

                    "name":
                        "desk",

                    "description":
                        "Desk with flat top.",
                },
            ],
            compact_dna=[
                {
                    "item_id":
                        "blanket_01",

                    "traits": [
                        "soft",
                        "flexible",
                    ],

                    "capabilities": [
                        "cover",
                        "hang",
                    ],

                    "unknown_properties":
                        [],

                    "caution_notes":
                        [],
                },
                {
                    "item_id":
                        "desk_01",

                    "traits": [
                        "flat",
                    ],

                    "capabilities": [
                        "provide_surface",
                    ],

                    "unknown_properties": [
                        (
                            "load-bearing capacity"
                        )
                    ],

                    "caution_notes":
                        [],
                },
            ],
            external_resources=[
                "smartphone",
            ],
            semantic_field_map=(
                field_map
            ),
        )
    )

    normalized_prompt = (
        " ".join(
            prompt.split()
        )
    )

    required_phrases = [
        (
            "MANDATORY FIELD-BY-FIELD AUDIT"
        ),
        (
            '"coverage" object with EXACTLY the same '
            "field IDs"
        ),
        (
            "ZERO will deterministically reject "
            "your entire response"
        ),
        (
            "The model's own \"passed\" judgment "
            "is NOT requested"
        ),
        (
            "The window diffuses available light."
        ),
        (
            "The window provides illumination."
        ),
        (
            "Provides a uniform background."
        ),
    ]

    for phrase in required_phrases:
        assert phrase in normalized_prompt, (
            f"Missing semantic coverage rule: {phrase}"
        )

    for field_id in field_map:
        assert (
            f'"{field_id}"'
            in prompt
        ), (
            "Required field ID missing from prompt: "
            f"{field_id}"
        )

def test_empty_known_aggregate_keys_are_allowed():
    field_ids = list(
        _build_semantic_field_map(
            build_plan()
        ).keys()
    )

    coverage = {
        field_id: []
        for field_id in field_ids
    }

    coverage[
        "assumption"
    ] = []

    coverage[
        "constraint_check"
    ] = []

    envelope = SemanticAuditEnvelope(
        findings=[],
        coverage=coverage,
    )

    _validate_semantic_coverage(
        envelope=envelope,
        required_field_ids=field_ids,
    )


def test_nonempty_known_aggregate_key_is_rejected():
    field_ids = list(
        _build_semantic_field_map(
            build_plan()
        ).keys()
    )

    coverage = {
        field_id: []
        for field_id in field_ids
    }

    coverage[
        "assumption"
    ] = [1]

    envelope = SemanticAuditEnvelope(
        findings=[
            build_finding()
        ],
        coverage=coverage,
    )

    try:
        _validate_semantic_coverage(
            envelope=envelope,
            required_field_ids=field_ids,
        )

    except IncompleteSemanticCoverageError:
        return

    raise AssertionError(
        "Non-empty aggregate coverage key was accepted."
    )


def test_aggregate_key_does_not_replace_missing_exact_field():
    field_ids = list(
        _build_semantic_field_map(
            build_plan()
        ).keys()
    )

    coverage = {
        field_id: []
        for field_id in field_ids
    }

    del coverage[
        "assumption:1"
    ]

    coverage[
        "assumption"
    ] = []

    envelope = SemanticAuditEnvelope(
        findings=[],
        coverage=coverage,
    )

    try:
        _validate_semantic_coverage(
            envelope=envelope,
            required_field_ids=field_ids,
        )

    except IncompleteSemanticCoverageError:
        return

    raise AssertionError(
        "Aggregate assumption key incorrectly replaced "
        "missing assumption:1."
    )


def test_unknown_empty_extra_key_is_still_rejected():
    field_ids = list(
        _build_semantic_field_map(
            build_plan()
        ).keys()
    )

    coverage = {
        field_id: []
        for field_id in field_ids
    }

    coverage[
        "totally_unknown_group"
    ] = []

    envelope = SemanticAuditEnvelope(
        findings=[],
        coverage=coverage,
    )

    try:
        _validate_semantic_coverage(
            envelope=envelope,
            required_field_ids=field_ids,
        )

    except IncompleteSemanticCoverageError:
        return

    raise AssertionError(
        "Unknown empty aggregate key was accepted."
    )


def run_tests():
    tests = [
        (
            "semantic field map exact",
            test_field_map_is_exact_and_complete,
        ),
        (
            "valid exact coverage",
            test_valid_exact_coverage_passes,
        ),
        (
            "missing field rejected",
            test_missing_field_is_rejected,
        ),
        (
            "unknown field rejected",
            test_unknown_extra_field_is_rejected,
        ),
        (
            "invalid finding reference rejected",
            test_invalid_finding_reference_is_rejected,
        ),
        (
            "zero finding reference rejected",
            test_zero_finding_reference_is_rejected,
        ),
        (
            "duplicate reference rejected",
            test_duplicate_reference_is_rejected,
        ),
        (
            "unattached finding rejected",
            test_unattached_finding_is_rejected,
        ),
        (
            "empty findings exact coverage",
            test_no_findings_with_full_coverage_passes,
        ),
        (
            "medium finding derives failure",
            test_parse_derives_failed_result_from_medium_finding,
        ),
        (
            "low-only finding derives pass",
            test_parse_derives_pass_from_low_only_finding,
        ),
        (
            "prompt exact coverage contract",
            test_prompt_contains_exact_coverage_contract,
        ),
        (
            "empty known aggregate keys allowed",
            test_empty_known_aggregate_keys_are_allowed,
        ),
        (
            "non-empty aggregate key rejected",
            test_nonempty_known_aggregate_key_is_rejected,
        ),
        (
            "aggregate key cannot replace exact field",
            test_aggregate_key_does_not_replace_missing_exact_field,
        ),
        (
            "unknown empty extra key rejected",
            test_unknown_empty_extra_key_is_still_rejected,
        ),
    ]

    passed = 0

    for name, test in tests:
        test()

        passed += 1

        print(
            f"PASS: {name}"
        )

    print()
    print(
        f"{passed}/{len(tests)} tests passed."
    )

    print(
        "Model calls: 0"
    )


if __name__ == "__main__":
    run_tests()