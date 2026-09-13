# Walkthrough 02 Object DNA Freeze

## Status

Walkthrough 02 Object DNA is frozen for downstream capability and planning work.

Object DNA remains goal-independent.

No paid Object DNA rerun is required unless the canonical/session inventory,
Object DNA source pipeline, or human evidence changes.

## Repository checkpoint

Production source commit:

`984523d` — `Harden Object DNA light-blocking semantics`

The commit was pushed successfully to `origin/main`.

## Walkthrough

Walkthrough ID:

`walkthrough-02`

Private video:

`sample_data/private/walkthrough-02.mov`

## Canonical inventory

Canonical inventory:

`sample_data/private/walkthrough-02-canonical-inventory.json`

Canonical inventory SHA-256:

`77b9dee2b8f491ed5c43a0b0f38f8c64587eea18378867c44f47286efcada927`

Session inventory:

- 81 total canonical items
- 33 AUTO_ACCEPTED
- 2 USER_CONFIRMED
- 46 NEEDS_CONFIRMATION
- 35 eligible for Object DNA

The two user-confirmed items are:

- `red_reusable_shopping_bag_f08_o04`
- `folded_fabric_f08_o13`, corrected by the user to `blanket`

`coat_rack_f06_o06` was corrected by the user to a vacuum rack/stand,
but was not explicitly confirmed and therefore remains
NEEDS_CONFIRMATION and is excluded from Object DNA/planning eligibility.

## Final Object DNA pipeline

Final Object DNA pipeline SHA-256:

`afb24b158a8abf8dedcfc415923fe5872d1b56437cdddf2f1c29b7d8b6bc2553`

Final valid per-item cache coverage:

`35/35`

Final aggregate snapshot:

`sample_data/private/walkthrough-02-session-object-dna.json`

Final aggregate SHA-256:

`be3550aa51e0b473f3ad0f379db87572725cf2eeaa4852d268ebb9fcc3c725bf`

Per-item caches remain authoritative.

## Final semantic guardrails

The frozen Object DNA pipeline includes deterministic protection for:

- destructive or externally-added HANG assumptions
- unsupported SUPPORT/ELEVATE semantics
- ELEVATE geometry requirements
- load-bearing uncertainty
- electrical rating and condition uncertainty
- container/current-content uncertainty
- flexible cover dimensions and coverage uncertainty
- PROVIDE_SURFACE geometry
- PROVIDE_WEIGHT requiring both WEIGHTED and PORTABLE
- BLOCK_LIGHT requiring:
  - OPAQUE
  - LARGE_SURFACE
  - and at least one of FLEXIBLE, MOVABLE, or PORTABLE
- semantic deduplication of equivalent unknown-property strings

The final block-light hardening removed invalid BLOCK_LIGHT affordances
from fixed structural surfaces including:

- `wall_f01_o04`
- `wood_flooring_f03_o14`

The final migration also deduplicated unknown-property variants for:

- `trash_can_f02_o02`
- `insulated_water_bottle_f08_o05`

## Cache migration

The immediately preceding complete pipeline was:

`58ec2a3a09a26fb0a96fe97e3b454672b01128364a9648b2bf8b3cc0873feced`

All 35 caches from that pipeline were archived before the final hardening.

Migration dry-run:

- 35 archived entries
- 35 migratable
- 4 changed by the stricter deterministic sanitizer
- 0 failed
- 0 model calls

Production migration:

- 35 migrated
- 4 changed
- 0 model calls

A post-migration dry-run confirmed:

- 35 eligible Object DNA items
- 35 valid cache hits
- 0 missing/stale
- 0 expected new calls

## Downstream goal

The next downstream planning goal is:

`Create a temporary curtain using only what I already have, without spending money or drilling, while minimizing the risk of damaging painted surfaces.`

Object DNA itself was generated independently of this goal.

## Freeze rule

Do not regenerate the 35 Walkthrough 02 Object DNA entries merely to
continue planning.

Downstream capability/planning work should consume this frozen evidence.

If a later source change invalidates the pipeline fingerprint, preserve the
current caches and aggregate as historical evidence before any migration or
paid regeneration.
