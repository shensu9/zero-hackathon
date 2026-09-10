import hashlib
import json
import subprocess
from pathlib import Path

import benchmark_suite as suite

from plan_evaluator import EVALUATOR_VERSION
from unseen_benchmark_cases import (
    UNSEEN_BENCHMARK_CASES,
)


SUITE_ID = "unseen_benchmark_01"

EXPECTED_EVALUATOR_VERSION = (
    "neutral_evaluator_v2"
)


REPO_ROOT = Path(
    __file__
).resolve().parents[2]

CASE_SOURCE_PATH = (
    REPO_ROOT
    / "services"
    / "api"
    / "unseen_benchmark_cases.py"
)

RESULTS_DIR = (
    REPO_ROOT
    / "results"
    / SUITE_ID
)


# ---------------------------------------------------------------------------
# REPRODUCIBILITY
# ---------------------------------------------------------------------------


def _run_git(
    *args: str,
) -> str:
    result = subprocess.run(
        [
            "git",
            *args,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout.strip()


def get_git_commit() -> str:
    return _run_git(
        "rev-parse",
        "HEAD",
    )


def require_clean_working_tree() -> None:
    """
    The unseen benchmark must begin from a clean committed repository.

    This prevents changing ZERO, the evaluator, or the benchmark cases
    and then silently running under an unrecorded state.
    """

    status = _run_git(
        "status",
        "--porcelain",
    )

    if status:
        raise RuntimeError(
            "Unseen benchmark requires a clean Git working tree. "
            "Commit or restore all changes before running."
        )


def sha256_file(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


# ---------------------------------------------------------------------------
# PROTOCOL
# ---------------------------------------------------------------------------


def build_protocol() -> dict:
    return {
        "suite_id":
            SUITE_ID,

        "git_commit":
            get_git_commit(),

        "evaluator_version":
            EVALUATOR_VERSION,

        "evaluator_policy":
            (
                "Frozen neutral evaluator v2. "
                "Previously passed 6/6 calibration and "
                "6/6 independent holdout."
            ),

        "benchmark_type":
            "unseen",

        "benchmark_case_ids": [
            case.case_id
            for case in UNSEEN_BENCHMARK_CASES
        ],

        "benchmark_case_count":
            len(UNSEEN_BENCHMARK_CASES),

        "benchmark_case_source":
            "services/api/unseen_benchmark_cases.py",

        "benchmark_case_source_sha256":
            sha256_file(
                CASE_SOURCE_PATH
            ),

        "case_freeze_policy":
            (
                "Unseen cases were committed before any "
                "baseline or ZERO generation for this suite."
            ),

        "object_dna_policy":
            "fixed validated fixture cache",

        "baseline_policy":
            "fresh generation for every unseen case",

        "zero_policy":
            (
                "fresh capability-bound generation, "
                "deterministic validation, semantic critic, "
                "maximum two repair attempts"
            ),

        "external_resource_normalization":
            (
                "enabled symmetrically for baseline, ZERO, "
                "and repair candidates"
            ),

        "comparative_scoring":
            (
                "neutral evaluator only; "
                "ZERO internal critic is not used as "
                "the comparative benchmark judge"
            ),

        "prior_benchmark_outputs_reused":
            False,

        "expected_labels_sent_to_models":
            False,

        "human_rationales_sent_to_models":
            False,
    }


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------


def main() -> None:
    # ---------------------------------------------------------------
    # HARD FREEZE CHECKS
    # ---------------------------------------------------------------

    if (
        EVALUATOR_VERSION
        != EXPECTED_EVALUATOR_VERSION
    ):
        raise RuntimeError(
            "Unseen benchmark requires "
            f"{EXPECTED_EVALUATOR_VERSION}, "
            f"but found {EVALUATOR_VERSION}."
        )

    require_clean_working_tree()

    if (
        RESULTS_DIR.exists()
        and any(
            RESULTS_DIR.iterdir()
        )
    ):
        raise RuntimeError(
            "Unseen benchmark results already exist. "
            "Do not overwrite immutable benchmark evidence."
        )

    # ---------------------------------------------------------------
    # POINT GENERIC SUITE AT FROZEN UNSEEN CASES
    # ---------------------------------------------------------------

    suite.SUITE_ID = SUITE_ID

    suite.RESULTS_DIR = (
        RESULTS_DIR
    )

    suite.BENCHMARK_CASES = (
        UNSEEN_BENCHMARK_CASES
    )

    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------------
    # RECORD PROTOCOL BEFORE MODEL CALLS
    # ---------------------------------------------------------------

    protocol = build_protocol()

    protocol_path = (
        RESULTS_DIR
        / "protocol.json"
    )

    protocol_path.write_text(
        json.dumps(
            protocol,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("ZERO FROZEN UNSEEN BENCHMARK")
    print("=" * 72)

    print(
        json.dumps(
            protocol,
            indent=2,
            ensure_ascii=False,
        )
    )

    print()

    # ---------------------------------------------------------------
    # RUN U01-U05
    # ---------------------------------------------------------------

    suite.main()


if __name__ == "__main__":
    main()