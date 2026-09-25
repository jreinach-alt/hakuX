# Audit pass 2 -- PR #288, lane/vshsubneg255 (#255)

Head verified: `f680a83e83`. Since the pass-1 head `99b2c6c659` the only
change is the pass-1 audit file itself; `pgraph.c`, the NOTES and the index
are byte-identical to what pass 1 read. MERGEABLE.

**Result: clean.** Pass 1 raised no HIGH and no MEDIUM, so there is no
failure scenario that pass 2 must show can no longer occur. Next state:
`fold-ready`.

## Re-check of the pass-1 reasoning on the unchanged code

Pass 1's "not a defect" conclusions were re-read against the same diff:

- The ILU copy (`ilu_full = *full`) is taken before the MAC-only apply, so
  the ILU still reads pre-step registers, including A0; the ILU copy-back
  runs last and is writemask-gated (`NV2AWM_X >> c`). Unchanged.
- `ilu_state` is initialised on `ilu_full` before the struct assignment, and
  the assignment copies arrays only, so its register pointers stay valid.
- `vsh_flush_outputs` has no remaining references; the input and constant
  pre-flushes are removed only in favour of the ILU-side `vsh_flush_all`.

## Disposition of the LOWs

- **LOW-1 (MAC arithmetic on subnormals is now unflushed).** Still true by
  design; it is an open accuracy question, not a regression, and the NOTES
  name the settling console run (CPU Shader Tests with
  `USE_EXCEPTIONAL_VALUES`). No issue for that run exists yet
  (searched 2026-09-25). Recommendation carried to the board: file one so
  the question has a row. It does not block the fold.
- **LOW-2 (no desktop test of the MAC/ILU split).** Still true; quality,
  does not block the fold.
