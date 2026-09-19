import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response


REPO_ROOT = Path(__file__).resolve().parents[2]


app = FastAPI(
    title="ZERO Demo",
    description="Offline evidence-backed demo for the ZERO hackathon project.",
    version="1.0.0",
)


DEMO_SCENARIOS = [
    {
        "id": "W1",
        "name": "Product photography",
        "status": "SOLVED",
        "goal": (
            "Create a $0 product photography setup at home using only "
            "what I already have, without permanent modifications."
        ),
        "summary": (
            "ZERO grounded a backdrop, lighting, and product surface "
            "using validated capabilities from the available environment."
        ),
        "decision_trace": [
            "Validated inventory and Object DNA coverage passed.",
            "Wardrobe door and blanket support the backdrop plan.",
            "Window provides grounded light-handling capability.",
            "Desk provides the required product surface.",
            "Final semantic findings: 0.",
        ],
    },
    {
        "id": "W2",
        "name": "Temporary curtain",
        "status": "CONDITIONAL",
        "goal": (
            "Create a temporary curtain using only what I already have, "
            "without spending money or drilling, while minimizing the "
            "risk of damaging painted surfaces."
        ),
        "summary": (
            "A plan exists, but execution is blocked until the door frame "
            "support and blanket fit are verified."
        ),
        "requirements": 2,
        "decision_trace": [
            "A physical plan exists.",
            "Verify the door frame is secure enough for the fabric.",
            "Verify the blanket is large enough to fit the frame.",
            "Execution remains blocked until both requirements pass.",
            "Final semantic findings: 0.",
        ],
    },
    {
        "id": "W3",
        "name": "Full-length mirror",
        "status": "CANNOT_SAFELY_SOLVE",
        "goal": (
            "Hang a full-length mirror on a painted wall using only what "
            "I already have, without drilling, adhesives, or buying "
            "anything, while making sure it cannot fall."
        ),
        "summary": (
            "No complete grounded attachment path could secure the mirror "
            "under the stated constraints."
        ),
        "decision_trace": [
            "The mirror has no grounded hang, mount, attach, or secure capability.",
            "Garment-oriented hook and rack capabilities do not prove mirror support.",
            "Load-bearing capacity and attachment method remain unknown.",
            "No complete constraint-compatible mirror-to-wall chain was established.",
            "Final blocker critic: PASS with 0 findings.",
        ],
    },
    {
        "id": "W4",
        "name": "Focal display choice",
        "status": "NEEDS_CONFIRMATION",
        "goal": (
            "Create one focal display using either the guitar or canvas "
            "artwork without damaging the wall."
        ),
        "summary": (
            "The user has not chosen which target to feature, so ZERO "
            "preserves the no-plan boundary and asks for that preference."
        ),
        "requirements": 1,
        "decision_trace": [
            "Both the acoustic guitar and canvas artwork are available.",
            "The user has not selected which item should be featured.",
            "That missing preference determines which plan should be selected.",
            "ZERO therefore keeps plan = null and asks the user.",
            "Confirmation critic: PASS with 0 findings.",
        ],
    },
]


def load_public_json(relative_path: str) -> dict:
    path = REPO_ROOT / relative_path
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "mode": "offline_evidence",
        "model_calls": 0,
    }


@app.get("/api/scenarios")
def scenarios() -> dict:
    return {
        "scenarios": DEMO_SCENARIOS,
    }


@app.get("/api/benchmarks")
def benchmarks() -> dict:
    repeated = load_public_json(
        "results/benchmark_repeated_01/summary.json"
    )
    suite_05 = load_public_json(
        "results/benchmark_suite_05/summary.json"
    )
    unseen = load_public_json(
        "results/unseen_benchmark_01/summary.json"
    )
    calibration = load_public_json(
        "results/evaluator_calibration_02/summary.json"
    )
    holdout = load_public_json(
        "results/evaluator_holdout_01/summary.json"
    )

    repeated_aggregate = repeated["aggregate"]
    suite_05_aggregate = suite_05["aggregate"]
    unseen_aggregate = unseen["aggregate"]

    return {
        "repeated": {
            "paired_case_runs": repeated["paired_case_runs"],
            "trials": repeated["trials"],
            "baseline_medium_high": repeated_aggregate[
                "baseline_total_medium_high"
            ],
            "zero_medium_high": repeated_aggregate[
                "zero_total_medium_high"
            ],
            "reduction_percent": repeated_aggregate[
                "reduction_percent"
            ],
            "zero_wins": repeated_aggregate["zero_wins"],
            "ties": repeated_aggregate["ties"],
            "baseline_wins": repeated_aggregate["baseline_wins"],
        },
        "suite_05": {
            "completed_cases": suite_05["completed_cases"],
            "total_cases": suite_05["total_cases"],
            "failed_cases": suite_05["failed_cases"],
            "baseline_medium_high": suite_05_aggregate[
                "baseline_medium_high_findings"
            ],
            "zero_medium_high": suite_05_aggregate[
                "zero_medium_high_findings"
            ],
            "reduction_percent": suite_05_aggregate[
                "medium_high_reduction_percent"
            ],
        },
        "unseen": {
            "completed_cases": unseen["completed_cases"],
            "total_cases": unseen["total_cases"],
            "failed_cases": unseen["failed_cases"],
            "zero_wins": unseen_aggregate["zero_wins_by_medium_high"],
            "ties": unseen_aggregate["ties_by_medium_high"],
            "baseline_wins": unseen_aggregate[
                "baseline_wins_by_medium_high"
            ],
        },
        "evaluator": {
            "calibration_matched": calibration["matched_cases"],
            "calibration_total": calibration["total_cases"],
            "holdout_matched": holdout["matched_cases"],
            "holdout_total": holdout["total_cases"],
        },
    }


@app.get("/", response_class=HTMLResponse)
def demo_home() -> HTMLResponse:
    html_path = Path(__file__).with_name("demo_index.html")
    return HTMLResponse(
        html_path.read_text(encoding="utf-8")
    )


@app.get("/demo.css")
def demo_css() -> Response:
    css_path = Path(__file__).with_name("demo.css")
    return Response(
        content=css_path.read_text(encoding="utf-8"),
        media_type="text/css",
    )


@app.get("/demo.js")
def demo_js() -> Response:
    js_path = Path(__file__).with_name("demo.js")
    return Response(
        content=js_path.read_text(encoding="utf-8"),
        media_type="application/javascript",
    )
