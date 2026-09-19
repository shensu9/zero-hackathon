# Walkthrough 04 - Terminal Freeze

## Status

TERMINAL PASS

Final ZERO outcome:

`NEEDS_CONFIRMATION`

Walkthrough 04 is frozen. No paid planner, confirmation-critic, perception, entity-resolution, Object DNA, or other semantic calls should be rerun for this preserved scenario.

---

## Goal

Create one focal display in this room using either the guitar or the canvas artwork, using only what I already have and without damaging the wall. I only want one focal item, but I have not decided which one I want to feature.

---

## Scenario design

Walkthrough 04 intentionally reuses the exact frozen physical world model from Walkthrough 03.

No new perception, entity resolution, human-confirmation processing, or Object DNA generation was required.

The new variable is the user goal.

The user explicitly allows either of two different focal targets:

- acoustic guitar
- canvas artwork

but has not selected which one should be featured.

That unresolved preference materially determines which physical plan ZERO should attempt to construct.

It is therefore different from a CONDITIONAL case, where ZERO already knows which physical plan it intends to execute and only needs a prerequisite verified.

---

## Terminal conclusion

ZERO returned:

`NEEDS_CONFIRMATION`

The initial planner explanation was:

> User has not decided whether to feature the guitar or the canvas artwork; ZERO cannot select a plan without this choice.

The preserved initial outcome contains:

- status: `needs_confirmation`
- plan: none
- requirements: 1
- blocking reasons: 0

The single requirement is:

> Determine which item to feature as the focal display: acoustic guitar or canvas artwork.

Verification method:

> User states their preference for either the guitar or the canvas artwork.

If the requirement is not met:

> ZERO awaits clarification before proposing any physical plan.

The outcome was not accepted from schema validity alone.

It passed the dedicated production NEEDS_CONFIRMATION semantic-grounding audit with zero findings.

---

## Planning evidence

W4 planning input SHA256:

`4b8c0d7b0e328693644432f13430d3a5122331a9852080900a4b1e7701b86a67`

Initial planner pipeline SHA256:

`8ab2fe1630773d6d30f68f7926e3bb5c762bc06de87cb35d19c3471017953d35`

Initial planner cache:

`sample_data/private/walkthrough-04-initial-plan-outcome.json`

Initial planner cache SHA256:

`1e1a9c8fa6b8f544f6d29f28477bbe482f448e4db3c00f1e22f2d357dbe37886`

Initial PlanOutcome SHA256:

`59500a819fa3c0a09e459470d09c58212794826b1a12be1266e60a038ecf4e0e`

The initial planner cache must remain preserved and must not be regenerated.

---

## Frozen source world

Source walkthrough:

`walkthrough-03`

Canonical inventory SHA256:

`6c3a4d47bfc46e59f666ef44fe1bc8ba989be527242160299d625e54bfc727df`

Session inventory SHA256:

`a27c535683216f4871d4855ee69803b85ca55d2f1de25f2637f2e98ec47752e5`

Planner-canonicalized Object DNA SHA256:

`24ee7c57b96f05518f47b0821932a4f4b77eccf2fe82ca257193828dc82bd6a2`

Active eligible inventory items:

`27`

Validated Object DNA records:

`27`

Required W4 target candidates present in that frozen world:

- `canvas_artwork_f05_o01`
- `acoustic_guitar_f06_o05`

Walkthrough 04 does not create a second copy of the physical world evidence.

It references the frozen W3 world while using a separate goal, planning input, planner cache, and semantic-audit cache.

---

## NEEDS_CONFIRMATION production hardening

Before W4, production handling for a plan-less NEEDS_CONFIRMATION outcome would have inherited the generic plan-audit behavior, which automatically passed when `plan=None`.

That created the same class of semantic gap previously exposed by negative outcomes.

Production hardening added a dedicated semantic audit for NEEDS_CONFIRMATION.

Hardening commit:

`3174313` - Audit needs-confirmation outcomes

The audit checks that:

- the claimed missing information is genuinely unresolved;
- the information materially determines WHICH physical plan or target should be selected;
- the information is not already grounded in the available evidence;
- the case is not merely a CONDITIONAL prerequisite for an already-selected plan;
- the case is not actually CANNOT_SAFELY_SOLVE;
- multiple possible plans alone do not manufacture ambiguity;
- a user-preference requirement can be verified by asking the user;
- the requirement's `if_not_met` behavior preserves the no-plan boundary;
- MEDIUM/HIGH semantic findings fail the audit.

The critic performs at most one preserved semantic call for this W4 audit version.

---

## W4 runner checkpoints

Initial W4 planner runner commit:

`5b9edc2` - Add walkthrough 04 initial planner runner

W4 confirmation-audit runner commit:

`1eeede8` - Add walkthrough 04 confirmation audit runner

Both runners fail closed on stale or mismatched evidence and preserve their private caches rather than silently overwriting them.

---

## Final confirmation semantic audit

Confirmation-audit input SHA256:

`b5be1f1af67f36ab33bb49e012b57cab2b8a7d147fcd7834b7363312c424893e`

Confirmation critic pipeline SHA256:

`aa4eff3bcdc8847139034b02ba67c60f2ab523be56ab8945b688118445e065e7`

Confirmation critic cache:

`sample_data/private/walkthrough-04-needs-confirmation-critic.json`

Confirmation critic cache SHA256:

`7e01bcb717512ed4c3257bf670eaa02d9b698734f57f9048b9e0a8e068107bb2`

Canonical critic result SHA256:

`3def2a20106f4de4b153ea201a2acadea4ea2508331010c8ea7ed70b4053bd28`

Result:

- passed: true
- findings: 0

The dedicated critic therefore semantically grounded the preserved NEEDS_CONFIRMATION outcome.

---

## Paid-call record

Walkthrough 04 reused the already-frozen W3 world model.

New paid calls made specifically for W4 terminalization:

- initial PlanOutcome generation: 1
- NEEDS_CONFIRMATION semantic critic: 1

New paid calls not made:

- perception: 0
- cross-frame entity resolution: 0
- Object DNA: 0
- semantic repair: 0
- verification-gate repair: 0
- requirement repair: 0

Total new W4 model calls:

`2`

---

## Engineering interpretation

Walkthrough 04 demonstrates a valid decision-boundary case.

ZERO has not yet chosen a physical plan because the user has not chosen the target that the plan must operate on.

The missing information is therefore plan-selecting information rather than merely plan-validating information.

This is the defining distinction between:

`NEEDS_CONFIRMATION`

and:

`CONDITIONAL`

The result does not claim that either target is automatically safe to display after selection.

Once the user chooses a target, any subsequent physical plan must still independently satisfy grounding, safety, capability, and wall-damage constraints.

---

## Paid-call preservation rule

Do not rerun any paid Walkthrough 04 terminalization stage.

In particular, do not rerun:

- the W4 initial planner;
- the W4 NEEDS_CONFIRMATION semantic critic;
- W3 perception for the purpose of recreating W4;
- W3 entity resolution for the purpose of recreating W4;
- W3 Object DNA for the purpose of recreating W4.

The preserved W4 caches are the authoritative experiment evidence.

If a future user choice such as guitar or canvas is supplied, treat that as a new downstream planning scenario rather than overwriting this frozen NEEDS_CONFIRMATION evidence.

---

## Terminal freeze

Walkthrough 04 terminal state:

`NEEDS_CONFIRMATION`

Final confirmation semantic audit:

`PASS`

Final confirmation findings:

`0`

No further W4 semantic repair, reclassification, requirement promotion, planner rerun, or paid audit is authorized for this preserved scenario.

Walkthrough 04 is frozen.