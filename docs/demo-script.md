# ZERO Hackathon Demo Script

Target length: approximately 2:30-3:00

## Demo structure

1. Problem and idea
2. W1 hosted decision trace - SOLVED
3. W2 - CONDITIONAL
4. W3 - CANNOT_SAFELY_SOLVE
5. W4 - NEEDS_CONFIRMATION
6. Benchmark evidence and closing

---

## 0:00-0:20 - Opening

**Visual:** Open the hosted ZERO demo at the hero, then pause on the "How ZERO reasons" flow.

**Narration:**

"AI can look at a room and suggest clever physical solutions. But it can also imagine capabilities that were never actually established."

"ZERO adds an evidence boundary: first model what each object can do, then let the planner use only validated capabilities."

---

## 0:20-1:00 - W1: Product photography

**Visual:** Scroll to W1, open "View decision trace", and show the grounded SOLVED reasoning steps.

**Goal:** Create a $0 product photography setup using only what is already available, with no permanent modifications.

**Narration:**

"ZERO turns the walkthrough into a canonical inventory and capability graph."

"For this goal, the blanket and wardrobe door provide the backdrop, the window provides grounded light handling, and the desk provides the product surface."

"Because each object use is supported by the validated world model, ZERO returns a solved plan."

**Result:** `SOLVED`

---

## 1:00-1:25 - W2: Temporary curtain

**Visual:** Close W1, open W2, and show the `CONDITIONAL` trace with its two verification requirements.

**Goal:** Create a temporary curtain using only what is already available, without spending money or drilling, while minimizing damage to painted surfaces.

**Narration:**

"ZERO finds a possible curtain plan, but two facts still matter before execution."

"The door frame must be secure enough for the fabric, and the blanket must fit across it."

"So ZERO returns a conditional plan and blocks execution until both are verified."

**Result:** `CONDITIONAL`

**Requirements:** 2

- Verify the door frame can support the fabric without damage.
- Verify the blanket is large enough to cover the frame.

---

## 1:25-1:50 - W3: Full-length mirror

**Visual:** Open W3 and hold on the `CANNOT_SAFELY_SOLVE` trace, especially the steps explaining why garment hooks and racks are insufficient evidence.

**Goal:** Hang a full-length mirror on a painted wall using only what is already available, without drilling, adhesives, or buying anything, while making sure it cannot fall.

**Narration:**

"This is where ZERO fails closed."

"Garment hooks and racks exist, but that does not prove they can secure a full-length mirror."

"No complete, constraint-compatible attachment path to the wall is grounded without inventing load capacity or attachment strength."

"So ZERO refuses to produce a physical plan."

**Result:** `CANNOT_SAFELY_SOLVE`

**Final blocker audit:** PASS, 0 findings

---

## 1:50-2:10 - W4: Focal display choice

**Visual:** Open W4 and show the `NEEDS_CONFIRMATION` trace explaining that the missing guitar-versus-canvas preference selects the plan.

**Goal:** Create one focal display using either the guitar or the canvas artwork, without damaging the wall, but the user has not chosen which item to feature.

**Narration:**

"W4 reuses the same world as W3 and changes only the goal."

"The guitar and canvas are both available, but the user has not chosen which one to feature."

"That missing preference selects the plan itself, so ZERO asks the user instead of guessing."

**Result:** `NEEDS_CONFIRMATION`

**Requirement:** Choose either the acoustic guitar or the canvas artwork.

**Confirmation audit:** PASS, 0 findings

---

## 2:10-2:45 - Benchmark evidence and closing

**Visual:** Return to the four outcome cards, then scroll to the benchmark evidence panel and hold on the 63.2% reduction.

**Narration:**

"I compared ZERO with a generic planner using the same Nemotron model, goals, inventory, external resources, and blind neutral evaluator."

"Across fifteen paired runs, medium-or-high findings fell from nineteen to seven, a 63.2 percent reduction."

"ZERO had fewer findings in ten runs, tied four, and had more in one."

"The point is not to force a solution. It is to know when to solve, verify, ask, or refuse."

"ZERO keeps creativity inside an evidence boundary."

**On-screen benchmark:**

```text
15 paired runs

Baseline medium/high findings: 19
ZERO medium/high findings:      7
Reduction:                     63.2%

ZERO wins:                     10
Ties:                           4
Baseline wins:                  1
```

**Final card:**

SOLVED | CONDITIONAL | NEEDS_CONFIRMATION | CANNOT_SAFELY_SOLVE

Reason freely about combinations. Never invent the physical capabilities that make them work.
