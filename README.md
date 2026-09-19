# ZERO

**AI that reasons about what the things around you can do, then solves physical goals using only what you already have.**

ZERO turns a walkthrough of a real environment into a grounded physical world model, then plans against that world instead of relying on object names and imagination alone.

## Live demo

**Hosted demo:** https://zero-hackathon-demo.onrender.com

The hosted demo is an offline, evidence-backed interface over ZERO's committed frozen walkthrough and benchmark results. It makes **0 model calls** and does not read private caches.

---

The core idea is simple:

> Before an AI tells you what to do with an object, it should prove that the object has a validated capability that authorizes that use.

---

## Why ZERO

General-purpose language models are good at proposing creative physical solutions, but they can also silently assume that:

- an object is strong enough;
- a surface is stable;
- a bottle contains the expected liquid;
- a cord can safely act as a fastener;
- an object can support, hold, clamp, hang, protect, or power something simply because that use seems plausible.

ZERO adds an evidence boundary between perception and planning.

Instead of asking only:

> "What objects are here?"

ZERO also asks:

> "What physical properties and capabilities are actually supported by evidence?"

The planner can then use only those validated capabilities.

---

## Architecture

ZERO separates probabilistic model reasoning from deterministic enforcement.

Model output is treated as untrusted until it passes typed schemas and deterministic validators.
```text
GOAL
  |
  v
WALKTHROUGH VIDEO
  |
  v
KEYFRAMES
  |
  v
PER-FRAME PERCEPTION
  |
  v
CROSS-FRAME ENTITY RESOLUTION
  |
  v
CANONICAL INVENTORY
  |
  v
CONFIRMATION BOUNDARY
  |
  v
OBJECT DNA
  |
  v
CAPABILITY-BOUND PLANNER
  |
  v
VERIFY / REPAIR
  |
  v
FINAL OUTCOME
```

---

## Object DNA

Each eligible inventory item can receive an **Object DNA** record containing evidence-backed information such as:

- physical traits;
- supported capabilities / affordances;
- certainty levels;
- unknown properties;
- caution notes.

A planner cannot use an inventory object merely because its identity suggests a possible use.

Every physical use must cite a capability that exists in that object's validated Object DNA.

Low-certainty capabilities cannot authorize physical actions.

---

## Outcome-aware planning

ZERO does not force every goal into an executable plan.

The planner can return four terminal states:

### `SOLVED`

A grounded plan can be executed with the available evidence and resources.

### `CONDITIONAL`

A plan is known, but execution depends on one or more concrete requirements being verified first.

### `NEEDS_CONFIRMATION`

ZERO cannot yet determine which physical plan should be selected because required information or user intent is unresolved.

### `CANNOT_SAFELY_SOLVE`

The required capability is absent, the constraints make the goal impossible, or no reasonable verification can convert the current inventory into a grounded safe solution.

This distinction prevents uncertainty from being silently converted into assumptions.

---

## Human confirmation boundary

Model confidence is **not** treated as user confirmation.

Inventory observations marked `NEEDS_CONFIRMATION` are excluded from physical reasoning until they are explicitly resolved.

The production orchestrator partitions inventory before Object DNA or planning.

```text
AUTO_ACCEPTED / USER_CONFIRMED
        |
        v
eligible for downstream reasoning

NEEDS_CONFIRMATION
        |
        v
excluded until resolved
```

This prevents uncertain observations from leaking into planning.

---

## Frozen walkthrough evidence

Four preserved walkthrough scenarios exercise all four terminal outcome states.

| Walkthrough | Goal type | Terminal state |
|---|---|---|
| W1 | Product photography | `SOLVED` |
| W2 | Temporary curtain | `CONDITIONAL` |
| W3 | Full-length mirror | `CANNOT_SAFELY_SOLVE` |
| W4 | Focal display choice | `NEEDS_CONFIRMATION` |

The offline frozen-suite validator checks preserved hashes, expected terminal semantics, and critic/gate results without making model calls.

Run:

```powershell
python -u services\api\walkthrough_frozen_suite_run.py
```

Expected summary:

```text
W1  Product photography
    Terminal state: SOLVED
    Evidence: PASS

W2  Temporary curtain
    Terminal state: CONDITIONAL
    Evidence: PASS

W3  Full-length mirror
    Terminal state: CANNOT_SAFELY_SOLVE
    Evidence: PASS

W4  Focal display choice
    Terminal state: NEEDS_CONFIRMATION
    Evidence: PASS

FROZEN SUITE RESULT: PASS
Frozen walkthroughs: 4/4 valid
Model calls: 0
```

Detailed freeze records are stored under `docs/checkpoints/`.

---

## Orchestrator safety boundary

`services/api/zero_orchestrator.py` is the downstream ZERO orchestration boundary.

It:

1. receives a canonical inventory and goal;
2. removes unresolved `NEEDS_CONFIRMATION` observations;
3. requires Object DNA coverage to exactly match eligible inventory;
4. sends only eligible objects into guarded planning;
5. returns active inventory, pending confirmations, Object DNA, and planning output.

The deterministic orchestrator handoff test reconstructs a preserved real session and verifies that unresolved observations cannot leak downstream.

Run:

```powershell
python -u services\api\zero_orchestrator_test.py
python -u services\api\walkthrough_orchestrator_handoff_run.py
```

The preserved handoff currently verifies:

```text
Canonical items: 85
Persisted USER_CONFIRMED items: 1
Active downstream items: 33
Pending confirmation items: 52
Pending items leaked downstream: 0
Planning/model calls: 0
```

The handoff runner deliberately uses synthetic zero-semantic Object DNA and a stub outcome.

It is an integration test of the orchestration contract, not a live end-to-end planner demo.

---

## Baseline vs ZERO evaluation

ZERO was compared against a generic physical-planning baseline.

Both approaches used:

- the same Nemotron planning model;
- the same user goal;
- the same canonical inventory;
- the same explicit external resources;
- the same frozen Object DNA world for neutral evaluation;
- the same blind neutral evaluator for comparative scoring.

The generic baseline receives inventory descriptions but does not receive Object DNA capability authorization.

ZERO additionally receives the validated capability graph and must satisfy:

- exact capability citations;
- deterministic inventory grounding;
- deterministic capability grounding;
- no low-certainty capability authorization;
- semantic critique;
- bounded repair.

ZERO's internal critic is not used as the comparative benchmark judge.

---

## Benchmark results

### Repeated benchmark

Three trials were run across five benchmark goals, producing 15 paired baseline-vs-ZERO runs.

```text
Baseline medium/high findings: 19
ZERO medium/high findings:      7
Absolute reduction:            12
Reduction:                     63.2%

ZERO wins:                     10
Ties:                           4
Baseline wins:                  1

Baseline accepted runs:       3/15 (20.0%)
ZERO accepted runs:           8/15 (53.3%)
```

The repeated trials used a frozen evaluator version, the same validated Object DNA fixture, fresh baseline and ZERO generations for each case, and no reuse of prior trial generations.

### One five-case benchmark trial

A later five-case run produced:

```text
Baseline medium/high findings: 7
ZERO medium/high findings:      2
Reduction:                     71.4%

Cases favoring ZERO:            4
Ties:                           1
Cases favoring baseline:        0
```

### Neutral evaluator validation

The frozen neutral evaluator was checked against small labeled sets before repeated comparison:

```text
Calibration: 6/6 matched
Holdout:     6/6 matched
```

These are small engineering validation sets, not a claim of general evaluator accuracy.

### Unseen benchmark

A separately frozen unseen suite was also attempted.

```text
Completed: 4/5
ZERO wins: 0
Ties:      4
Baseline wins: 0
```

One case failed before comparative completion because the generated physical plan contained zero steps and violated the `PhysicalPlan` schema.

The failure is preserved rather than removed or rerun.

This unseen suite therefore does not show an advantage for ZERO and is retained as negative evidence.

---

## Evidence preservation

ZERO intentionally preserves unsuccessful experiments as well as successful ones.

Important development policies:

- experiment caches are immutable evidence;
- valid paid-call caches are reused instead of regenerated;
- failed caches are retained;
- benchmark trial directories are immutable;
- frozen walkthrough hashes must continue to match;
- deterministic validation runs before unnecessary model retries.

Private model caches live under:

```text
sample_data/private/
```

and are intentionally excluded from Git.

---

## Models

Provider: Nebius Token Factory

Vision:

```text
MiniMaxAI/MiniMax-M3
```

Reasoning / planning / semantic evaluation:

```text
nvidia/nemotron-3-super-120b-a12b
```

Model reasoning is never treated as the final authority for structural or capability validity.

---

## Tech

- Python 3.13
- Pydantic
- OpenAI-compatible Nebius API
- OpenCV
- FastAPI / Uvicorn
- SHA-256 evidence fingerprints
- deterministic schema and capability validation

---

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
pip install -r services\api\requirements.txt
```

Run the offline evidence demo locally without an API key:

```powershell
pip install -r services\api\demo_requirements.txt
python -m uvicorn demo_app:app --app-dir services\api --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000`. This demo reads only committed public evidence and makes **0 model calls**.

Create a local `.env` containing a valid Nebius API key when running model-backed stages.

Do not commit `.env`.

---

## Free offline verification

These commands exercise important ZERO boundaries without intentionally making model calls:

```powershell
python -m py_compile services\api\zero_orchestrator.py services\api\zero_orchestrator_test.py services\api\walkthrough_orchestrator_handoff_run.py services\api\walkthrough_frozen_suite_run.py

python -u services\api\zero_orchestrator_test.py
python -u services\api\walkthrough_orchestrator_handoff_run.py
python -u services\api\walkthrough_frozen_suite_run.py
```

Do **not** use `plan_outcome_pipeline_test.py` as a free smoke test. It contains live/model-backed behavior.

---

## Current prototype boundary

ZERO is a hackathon prototype, not a general-purpose robotics safety system.

Current evidence demonstrates:

- video-to-inventory experimentation;
- cross-frame entity resolution;
- explicit human confirmation state;
- Object DNA world modeling;
- capability-bound planning;
- deterministic grounding validation;
- semantic auditing and bounded repair;
- outcome-aware refusal and clarification behavior;
- preserved benchmark and walkthrough evidence.

It does not prove safe operation for arbitrary environments, objects, or high-risk physical tasks.

The current orchestrator begins at the canonical-inventory boundary.

The full walkthrough pipeline that produces that inventory is implemented as separate staged components rather than one monolithic production service.

---

## Repository guide

```text
services/api/
    perception, inventory, Object DNA,
    planning, validation, critics, orchestration,
    benchmark and walkthrough runners

docs/checkpoints/
    frozen walkthrough evidence and hashes

results/
    benchmark, calibration, holdout,
    repeated-trial and unseen-suite results

sample_data/private/
    local preserved model evidence
    (gitignored)
```

---

## Core design principle

ZERO is not trying to make the model less creative.

It is trying to make creativity happen **inside an evidence boundary**.

> Reason freely about combinations — but never invent the physical capabilities that make those combinations work.
