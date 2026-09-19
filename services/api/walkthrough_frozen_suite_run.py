import hashlib
import json
import sys
from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

PRIVATE = (
    ROOT
    / "sample_data"
    / "private"
)

CHECKPOINTS = (
    ROOT
    / "docs"
    / "checkpoints"
)


class FrozenEvidenceError(
    RuntimeError
):
    pass


# ---------------------------------------------------------------------------
# EXPECTED FROZEN EVIDENCE
# ---------------------------------------------------------------------------


W1_PLANNING_INPUT_SHA256 = (
    "70c908075851996ecd0532c477977f03"
    "b5c428103ea792753310bbff3651e5e4"
)

W1_FINAL_PLAN_SHA256 = (
    "bff43374269a4ea71b9662824db5155"
    "b8aa68acb496cbfdfe03c4f5dc8ef31fd"
)

W1_GATE_OUTCOME_SHA256 = (
    "c4a53af26eee54fcc504d734124b61cb"
    "d966e3852c6c66abc47207c1d41e369a"
)

W1_GATE_PIPELINE_SHA256 = (
    "64198bc46a59a51261efb23b82910042"
    "2085c1618402e5233eaf81315e50a811"
)

W1_SEMANTIC_PIPELINE_SHA256 = (
    "713b1f02aa7b5444a3eb3c6f0fb71f1"
    "ce075a016e15f5b78f02c681be5355f1e"
)

W1_COMPATIBILITY_POLICY_SHA256 = (
    "c78cf6397ac1b033c39cf0a7d6a174e"
    "78d767753a31b68b31f4eff4a85849ee2"
)


W2_PLANNING_INPUT_SHA256 = (
    "227408ce1b2e01a9ec1ad75c270c77f"
    "56fed9553afbce04959b1907ce45466ad"
)

W2_FINAL_OUTCOME_SHA256 = (
    "f30982e31d20388f1f07b828f7e5cc6"
    "46630425c05dd2da71e04900cf1f53298"
)

W2_FINAL_EXECUTION_CONTEXT_SHA256 = (
    "2c02afc8a1ec5abea16c50b0736b779"
    "f476afe9d249010b509c4dff9a524af6e"
)

W2_GATE_PIPELINE_SHA256 = (
    "2d5082bee962e31c7f90dfe51775e318"
    "eb71cca8673180db87a3d56d9cb3ad58"
)

W2_FINAL_SEMANTIC_PIPELINE_SHA256 = (
    "4b8a656bfeb21083967cb784e40527739"
    "cae2ec859e4746ead5e45806eaf9b0e"
)

W2_REQUIREMENT_REPAIR_CACHE_SHA256 = (
    "b61865801e4646eb805d92d3897116c8"
    "ce597d155292c9bc6aabfda752353909"
)

W2_FINAL_GATE_CACHE_SHA256 = (
    "80877605f7d098e31d4c81428b562904"
    "aea870f91d225c10441e7298d5be2950"
)

W2_FINAL_SEMANTIC_CACHE_SHA256 = (
    "c3fa97af345e8addb746e317ff9cbb77"
    "0b1133083ceafd96f36fb28223aa903d"
)


W3_PLANNING_INPUT_SHA256 = (
    "9a0aa9a5e7ddb5706e3a3f2ae3b9739"
    "1157a249973fc4a0d831960035295b932"
)

W3_INITIAL_OUTCOME_SHA256 = (
    "38e15cb241a20492bff6da3535ca8c80"
    "87b3f6d10d2ce3cb0cc4b7946824b280"
)

W3_BLOCKER_INPUT_SHA256 = (
    "3ba6eb87d629bf208c1621389044d95f"
    "3f3016db3cbbc8367a1b5887bcfbc09f"
)

W3_V1_CACHE_SHA256 = (
    "78a980e9be2b3cd8faf204fc8a7c4f9c"
    "dca790ffcf113ba975100b5a1c92b769"
)

W3_V2_CACHE_SHA256 = (
    "d5f48b1d90c4c40fa84d11a42dc853"
    "9d84ac21e4579664003e7b7375c06253e6"
)

W3_V2_CRITIC_PIPELINE_SHA256 = (
    "0a9178add22fd0690341169235490025a"
    "28be6ccfd3c1c22d977c902ddc1350e"
)


# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------


W1_GATE_PATH = (
    PRIVATE
    / (
        "walkthrough-01-repair-closure-v5-"
        "verification-gate-after-repair-02.json"
    )
)

W1_FINAL_PATH = (
    PRIVATE
    / (
        "walkthrough-01-repair-closure-v5-"
        "final-semantic-critic-coverage-compat-"
        "retry-01.json"
    )
)

W2_REQUIREMENT_REPAIR_PATH = (
    PRIVATE
    / (
        "walkthrough-02-verification-requirement-"
        "repair-after-promotion-preserved.json"
    )
)

W2_GATE_PATH = (
    PRIVATE
    / (
        "walkthrough-02-verification-gate-after-"
        "requirement-repair-preserved.json"
    )
)

W2_FINAL_PATH = (
    PRIVATE
    / (
        "walkthrough-02-final-semantic-recheck-"
        "after-verification-gate-preserved.json"
    )
)

W3_INITIAL_PATH = (
    PRIVATE
    / "walkthrough-03-initial-plan-outcome.json"
)

W3_V1_PATH = (
    PRIVATE
    / "walkthrough-03-cannot-safely-solve-critic.json"
)

W3_V2_PATH = (
    PRIVATE
    / (
        "walkthrough-03-cannot-safely-solve-"
        "critic-v2.json"
    )
)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------


def canonical_json(
    payload,
) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_text(
    text: str,
) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def sha256_json(
    payload,
) -> str:
    return sha256_text(
        canonical_json(
            payload
        )
    )


def sha256_file(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise FrozenEvidenceError(
            message
        )


def expect_equal(
    actual,
    expected,
    label: str,
) -> None:
    if actual != expected:
        raise FrozenEvidenceError(
            f"{label} mismatch. "
            f"Expected={expected!r}, "
            f"actual={actual!r}"
        )


def load_json(
    path: Path,
) -> dict:
    require(
        path.exists(),
        f"Missing frozen artifact: {path}",
    )

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:
        raise FrozenEvidenceError(
            "Frozen artifact is not valid JSON: "
            f"{path}"
        ) from exc


def critic_passed(
    critic,
    *,
    label: str,
) -> None:
    require(
        isinstance(
            critic,
            dict,
        ),
        f"{label} critic is missing.",
    )

    expect_equal(
        critic.get(
            "passed"
        ),
        True,
        f"{label} passed",
    )

    expect_equal(
        critic.get(
            "findings"
        ),
        [],
        f"{label} findings",
    )


def audit_passed(
    audit,
    *,
    label: str,
) -> None:
    require(
        isinstance(
            audit,
            dict,
        ),
        f"{label} audit is missing.",
    )

    expect_equal(
        audit.get(
            "passed"
        ),
        True,
        f"{label} passed",
    )

    expect_equal(
        audit.get(
            "findings"
        ),
        [],
        f"{label} findings",
    )


def collect_outcomes(
    node,
) -> list[dict]:
    """
    Find embedded PlanOutcome-like dictionaries in a preserved cache.

    This is only structural inspection. It never imports ZERO runtime
    code and never performs model calls.
    """

    results: list[
        dict
    ] = []

    if isinstance(
        node,
        dict,
    ):
        if (
            node.get(
                "status"
            )
            in {
                "solved",
                "conditional",
                "needs_confirmation",
                "cannot_safely_solve",
            }
            and
            "requirements"
            in node
            and
            "blocking_reasons"
            in node
        ):
            results.append(
                node
            )

        for value in (
            node.values()
        ):
            results.extend(
                collect_outcomes(
                    value
                )
            )

    elif isinstance(
        node,
        list,
    ):
        for value in node:
            results.extend(
                collect_outcomes(
                    value
                )
            )

    return results


def require_freeze_documents(
) -> None:
    paths = [
        (
            CHECKPOINTS
            / "walkthrough-v5-freeze.md"
        ),
        (
            CHECKPOINTS
            / "walkthrough-02-terminal-freeze.md"
        ),
        (
            CHECKPOINTS
            / "walkthrough-03-terminal-freeze.md"
        ),
    ]

    for path in paths:
        require(
            path.exists(),
            "Missing freeze document: "
            f"{path}",
        )


# ---------------------------------------------------------------------------
# WALKTHROUGH 01
# ---------------------------------------------------------------------------


def validate_w1() -> dict:
    gate = load_json(
        W1_GATE_PATH
    )

    final = load_json(
        W1_FINAL_PATH
    )

    expect_equal(
        gate.get(
            "planning_input_sha256"
        ),
        W1_PLANNING_INPUT_SHA256,
        "W1 planning input SHA256",
    )

    expect_equal(
        gate.get(
            "repaired_plan_sha256"
        ),
        W1_FINAL_PLAN_SHA256,
        "W1 final repaired-plan SHA256",
    )

    expect_equal(
        gate.get(
            "gate_pipeline_sha256"
        ),
        W1_GATE_PIPELINE_SHA256,
        "W1 gate pipeline SHA256",
    )

    outcome = gate.get(
        "output_outcome"
    )

    require(
        isinstance(
            outcome,
            dict,
        ),
        "W1 gate output outcome is missing.",
    )

    expect_equal(
        sha256_json(
            outcome
        ),
        W1_GATE_OUTCOME_SHA256,
        "W1 gate output outcome SHA256",
    )

    expect_equal(
        outcome.get(
            "status"
        ),
        "solved",
        "W1 terminal status",
    )

    require(
        isinstance(
            outcome.get(
                "plan"
            ),
            dict,
        ),
        "W1 SOLVED outcome has no plan.",
    )

    expect_equal(
        outcome.get(
            "requirements"
        ),
        [],
        "W1 requirements",
    )

    expect_equal(
        outcome.get(
            "blocking_reasons"
        ),
        [],
        "W1 blocking reasons",
    )

    audit_passed(
        gate.get(
            "audit"
        ),
        label="W1 verification gate",
    )

    expect_equal(
        gate.get(
            "gate_repair_attempts"
        ),
        0,
        "W1 gate repair attempts",
    )

    expect_equal(
        final.get(
            "planning_input_sha256"
        ),
        W1_PLANNING_INPUT_SHA256,
        "W1 final planning input SHA256",
    )

    expect_equal(
        final.get(
            "gate_output_outcome_sha256"
        ),
        W1_GATE_OUTCOME_SHA256,
        "W1 final gate-outcome SHA256",
    )

    expect_equal(
        final.get(
            "semantic_pipeline_sha256"
        ),
        W1_SEMANTIC_PIPELINE_SHA256,
        "W1 terminal semantic pipeline SHA256",
    )

    expect_equal(
        final.get(
            "compatibility_policy_sha256"
        ),
        W1_COMPATIBILITY_POLICY_SHA256,
        "W1 compatibility policy SHA256",
    )

    critic_passed(
        final.get(
            "critic"
        ),
        label="W1 terminal semantic critic",
    )

    return {
        "id":
            "W1",

        "name":
            "Product photography",

        "status":
            "SOLVED",

        "details":
            (
                "gate PASS, final semantic PASS"
            ),
    }


# ---------------------------------------------------------------------------
# WALKTHROUGH 02
# ---------------------------------------------------------------------------


def validate_w2() -> dict:
    requirement_repair = (
        load_json(
            W2_REQUIREMENT_REPAIR_PATH
        )
    )

    gate = load_json(
        W2_GATE_PATH
    )

    final = load_json(
        W2_FINAL_PATH
    )

    expect_equal(
        sha256_file(
            W2_REQUIREMENT_REPAIR_PATH
        ),
        W2_REQUIREMENT_REPAIR_CACHE_SHA256,
        "W2 requirement-repair cache SHA256",
    )

    expect_equal(
        sha256_file(
            W2_GATE_PATH
        ),
        W2_FINAL_GATE_CACHE_SHA256,
        "W2 final gate cache SHA256",
    )

    expect_equal(
        sha256_file(
            W2_FINAL_PATH
        ),
        W2_FINAL_SEMANTIC_CACHE_SHA256,
        "W2 final semantic cache SHA256",
    )

    expect_equal(
        gate.get(
            "planning_input_sha256"
        ),
        W2_PLANNING_INPUT_SHA256,
        "W2 planning input SHA256",
    )

    expect_equal(
        gate.get(
            "repaired_outcome_sha256"
        ),
        W2_FINAL_OUTCOME_SHA256,
        "W2 repaired outcome SHA256",
    )

    expect_equal(
        gate.get(
            "gate_pipeline_sha256"
        ),
        W2_GATE_PIPELINE_SHA256,
        "W2 gate pipeline SHA256",
    )

    audit_passed(
        gate.get(
            "audit"
        ),
        label="W2 verification gate",
    )

    expect_equal(
        final.get(
            "planning_input_sha256"
        ),
        W2_PLANNING_INPUT_SHA256,
        "W2 final planning input SHA256",
    )

    expect_equal(
        final.get(
            "repaired_outcome_sha256"
        ),
        W2_FINAL_OUTCOME_SHA256,
        "W2 final outcome SHA256",
    )

    expect_equal(
        final.get(
            "final_execution_context_sha256"
        ),
        W2_FINAL_EXECUTION_CONTEXT_SHA256,
        "W2 final execution-context SHA256",
    )

    expect_equal(
        final.get(
            "semantic_pipeline_sha256"
        ),
        W2_FINAL_SEMANTIC_PIPELINE_SHA256,
        "W2 final semantic pipeline SHA256",
    )

    critic_passed(
        final.get(
            "critic"
        ),
        label="W2 terminal semantic critic",
    )

    outcomes = (
        collect_outcomes(
            requirement_repair
        )
    )

    matching = [
        outcome
        for outcome
        in outcomes
        if (
            outcome.get(
                "status"
            )
            == "conditional"
            and
            isinstance(
                outcome.get(
                    "plan"
                ),
                dict,
            )
            and
            len(
                outcome.get(
                    "requirements",
                    []
                )
            )
            == 2
        )
    ]

    require(
        bool(
            matching
        ),
        "W2 preserved requirement-repair cache "
        "does not contain the expected final "
        "CONDITIONAL outcome with exactly "
        "two verification requirements.",
    )

    outcome = matching[-1]

    expect_equal(
        sha256_json(
            outcome
        ),
        W2_FINAL_OUTCOME_SHA256,
        "W2 reconstructed final outcome SHA256",
    )

    requirement_text = (
        canonical_json(
            outcome.get(
                "requirements",
                []
            )
        )
        .lower()
    )

    require(
        "door frame"
        in requirement_text,
        "W2 final requirements no longer "
        "contain the door-frame verification.",
    )

    require(
        "blanket"
        in requirement_text,
        "W2 final requirements no longer "
        "contain the blanket verification.",
    )

    return {
        "id":
            "W2",

        "name":
            "Temporary curtain",

        "status":
            "CONDITIONAL",

        "details":
            (
                "2 requirements, gate PASS, "
                "final semantic PASS"
            ),
    }


# ---------------------------------------------------------------------------
# WALKTHROUGH 03
# ---------------------------------------------------------------------------


def validate_w3() -> dict:
    initial = load_json(
        W3_INITIAL_PATH
    )

    v1 = load_json(
        W3_V1_PATH
    )

    v2 = load_json(
        W3_V2_PATH
    )

    expect_equal(
        initial.get(
            "planning_input_sha256"
        ),
        W3_PLANNING_INPUT_SHA256,
        "W3 planning input SHA256",
    )

    outcome = initial.get(
        "outcome"
    )

    require(
        isinstance(
            outcome,
            dict,
        ),
        "W3 initial outcome is missing.",
    )

    expect_equal(
        sha256_json(
            outcome
        ),
        W3_INITIAL_OUTCOME_SHA256,
        "W3 initial outcome SHA256",
    )

    expect_equal(
        outcome.get(
            "status"
        ),
        "cannot_safely_solve",
        "W3 terminal status",
    )

    expect_equal(
        outcome.get(
            "plan"
        ),
        None,
        "W3 plan",
    )

    expect_equal(
        outcome.get(
            "requirements"
        ),
        [],
        "W3 requirements",
    )

    require(
        len(
            outcome.get(
                "blocking_reasons",
                []
            )
        )
        == 1,
        "W3 must have exactly one frozen "
        "blocking reason.",
    )

    expect_equal(
        sha256_file(
            W3_V1_PATH
        ),
        W3_V1_CACHE_SHA256,
        "W3 preserved V1 cache SHA256",
    )

    v1_critic = v1.get(
        "critic"
    )

    require(
        isinstance(
            v1_critic,
            dict,
        ),
        "W3 V1 critic is missing.",
    )

    expect_equal(
        v1_critic.get(
            "passed"
        ),
        False,
        "W3 V1 critic passed",
    )

    require(
        len(
            v1_critic.get(
                "findings",
                []
            )
        )
        == 1,
        "W3 V1 must retain exactly one "
        "preserved finding.",
    )

    v1_finding = (
        v1_critic[
            "findings"
        ][0]
    )

    expect_equal(
        v1_finding.get(
            "severity"
        ),
        "medium",
        "W3 V1 finding severity",
    )

    expect_equal(
        v1_finding.get(
            "issue_type"
        ),
        "hidden_assumption",
        "W3 V1 finding type",
    )

    expect_equal(
        sha256_file(
            W3_V2_PATH
        ),
        W3_V2_CACHE_SHA256,
        "W3 V2 cache SHA256",
    )

    expect_equal(
        v2.get(
            "planning_input_sha256"
        ),
        W3_PLANNING_INPUT_SHA256,
        "W3 V2 planning input SHA256",
    )

    expect_equal(
        v2.get(
            "initial_outcome_sha256"
        ),
        W3_INITIAL_OUTCOME_SHA256,
        "W3 V2 initial outcome SHA256",
    )

    expect_equal(
        v2.get(
            "blocker_audit_input_sha256"
        ),
        W3_BLOCKER_INPUT_SHA256,
        "W3 V2 blocker input SHA256",
    )

    expect_equal(
        v2.get(
            "critic_pipeline_sha256"
        ),
        W3_V2_CRITIC_PIPELINE_SHA256,
        "W3 V2 critic pipeline SHA256",
    )

    critic_passed(
        v2.get(
            "critic"
        ),
        label="W3 V2 blocker critic",
    )

    return {
        "id":
            "W3",

        "name":
            "Full-length mirror",

        "status":
            "CANNOT_SAFELY_SOLVE",

        "details":
            (
                "V1 regression preserved, "
                "V2 blocker audit PASS"
            ),
    }


# ---------------------------------------------------------------------------
# SUITE
# ---------------------------------------------------------------------------


def main() -> None:
    print(
        "=" * 72
    )

    print(
        "ZERO FROZEN WALKTHROUGH SUITE"
    )

    print(
        "=" * 72
    )

    print()
    print(
        "Offline evidence validation only."
    )

    print(
        "No ZERO runtime/model modules are imported."
    )

    require_freeze_documents()

    results = []

    validators = [
        validate_w1,
        validate_w2,
        validate_w3,
    ]

    for validator in validators:
        result = validator()

        results.append(
            result
        )

        print()
        print(
            f"{result['id']}  "
            f"{result['name']}"
        )

        print(
            f"    Terminal state: "
            f"{result['status']}"
        )

        print(
            f"    Evidence: PASS"
        )

        print(
            f"    {result['details']}"
        )

    print()
    print(
        "=" * 72
    )

    print(
        "FROZEN SUITE RESULT: PASS"
    )

    print(
        f"Frozen walkthroughs: "
        f"{len(results)}/3 valid"
    )

    print(
        "Model calls: 0"
    )

    print(
        "=" * 72
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as exc:
        print()
        print(
            "=" * 72
        )

        print(
            "FROZEN SUITE RESULT: FAIL"
        )

        print(
            str(exc)
        )

        print(
            "Model calls: 0"
        )

        print(
            "=" * 72
        )

        sys.exit(
            1
        )