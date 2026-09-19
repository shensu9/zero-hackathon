# ZERO Hackathon Demo Script

Target length: approximately 2:30-3:00

## Demo structure

1. Problem and idea
2. W1 visual walkthrough - SOLVED
3. W2 - CONDITIONAL
4. W3 - CANNOT_SAFELY_SOLVE
5. W4 - NEEDS_CONFIRMATION
6. Benchmark evidence and closing

---

## 0:00-0:20 - Opening

**Visual:** ZERO title, then a short shot of the room.

**Narration:**

"AI can look at a room and suggest clever physical solutions. But it can also imagine capabilities that were never actually established."

"ZERO adds an evidence boundary: first model what each object can do, then let the planner use only validated capabilities."

---

## 0:20-1:00 - W1: Product photography

**Visual:** Play selected portions of `walkthrough-01.mov`, then show a few keyframes and the final plan.

**Goal:** Create a $0 product photography setup using only what is already available, with no permanent modifications.

**Narration:**

"ZERO turns the walkthrough into a canonical inventory and capability graph."

"For this goal, the blanket and wardrobe door provide the backdrop, the window provides grounded light handling, and the desk provides the product surface."

"Because each object use is supported by the validated world model, ZERO returns a solved plan."

**Result:** `SOLVED`

---

## 1:00-1:25 - W2: Temporary curtain

**Visual:** Show the W2 goal, then a compact result card with `CONDITIONAL` and the two verification requirements.

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

**Visual:** Show the mirror walkthrough briefly, then highlight the mirror, hook rack, and clothing rack with the final `CANNOT_SAFELY_SOLVE` result.

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

**Visual:** Reuse the W3 room world and highlight the acoustic guitar and canvas artwork, then show the `NEEDS_CONFIRMATION` result.

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

**Visual:** Show the four outcome states together, then the repeated benchmark numbers.

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
