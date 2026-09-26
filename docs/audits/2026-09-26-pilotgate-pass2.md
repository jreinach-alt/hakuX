# Audit pass 2: PR #420, lane/pilotgate

Head verified: `cbd328ab74` (remediation of pass 1, on top of a merge of
origin/master). Pass 1: `docs/audits/2026-09-26-pilotgate-pass1.md`, at
`0de649437d`.

**Verdict: clean. Neither MEDIUM scenario can occur on this head; L2 and L4 are
fixed; L1 and L3 stand as LOWs. Fold-ready once CI is green** (at the time of
writing `build` x2 and `selftest` were still in progress on `cbd328ab74`).

## How it was checked

- `selftest.d/99-pilot-gate.sh` was sourced alone against this head:
  15 passed, 0 failed.
- Three mutants of `request.sh` were run in a private detached worktree, one
  at a time. Each turns exactly its own leg red, and no other leg:
  - `PILOT_D=$D` (the gate counts the staging dir): F red. The staged soak is
    admitted into the empty staging queue.
  - The `arms-` exemption removed: G red. The arm is refused, and the refusal
    names `pilots/arms-pgx-base.ok`.
  - `est()` catching nothing useful: H red, with the Python traceback
    `ValueError: invalid literal for int() with base 10: '420s'`.
- `docs/lanes/titleplay/tools/queue.py` was driven end to end, not through the
  selftest's grep. It ran with `DISPATCH_DIR` set to a fake real dispatch dir
  and three plans of 420 s soaks on the `generic` route.

## MEDIUM 1 (queue.py runs the gate against its staging dir): closed

`queue.py` now passes `PILOT_DISPATCH_DIR=D` (the real dir) next to
`DISPATCH_DIR=stage`. `request.sh` sums `queue/` and `running/` in, and reads
`pilots/` from, `${PILOT_DISPATCH_DIR:-$D}`. The temp record is still read
from, and removed from, `$D`. The re-keyed record that `queue.py` renames into
the real queue keeps `requester: titleplay`, so every later line and every
later invocation counts it.

- **Split plan:** a 3-line plan was admitted (3 x 510 s = 1530 s). A second,
  separate invocation (a fresh staging tempdir) was refused on its first line:
  1530 + 510 = 2040 s. The real queue stayed at 3. This is the #397 shape, and
  it no longer gets through.
- **The pilot cannot be read:** the refusal named
  `/tmp/pg420/real/pilots/titleplay.ok`, which is the real dir, not the
  tempdir. Writing that file admitted the next invocation (real queue 3 → 4).
- Staged records left in `<stage>/queue/` are no longer counted, because the
  gate never reads the stage.

## MEDIUM 2 (arms records a pilot refusal as permanent): closed

`if who.startswith("arms-"): raise SystemExit(0)` comes before any sum. Both
arms.sh call sites use `--who "arms-$name-base"` / `"arms-$name-fix"`
(arms.sh:847, :850), so no arm can reach the refusal. `refused()` and its
`skipped/<sha>` marker therefore never record a queue-state refusal. Both
pass-1 scenarios (`runs_per_arm` ≥ 12 on an empty queue, and a 13th pooled
`arms-remote-*` arm) are admitted. Leg G covers the exemption, and the mutant
above shows the leg is not tautological. The rule text in AGENTS.md and
`roles/lane.md` now says arms are not judged, so the missing "what file lets an
arm past" text is moot.

## LOW follow-up

- **L2: fixed.** `est()` catches `TypeError`/`ValueError` and counts 180 s,
  and non-dict JSON is skipped (`isinstance(rq, dict)`). Leg H checks the
  words; the mutant above shows the leg catches the regression.
- **L4: fixed.** Leg A's fixtures are runs 3 (510 s), no `seconds` (180 s) and
  a running 511 s, landing the soak at 1801 s. The commit message reports that
  the `* runs` and 180 s mutants turn A red. I did not re-run those two.
- **L1: stands, and it is slightly wider.** The key is still the free-form
  `--who`. A hand caller can now also name itself `arms-anything` and not be
  judged. This is the same class as L1 (any caller can choose a name the gate
  does not pool), and it is documented. Arms are only ever queued by arms.sh.
  LOW.
- **L3: stands** (check-then-rename race between two concurrent hand callers
  of one requester). LOW.

## New in the remediation

Nothing above LOW. A caller that stages records privately and forgets
`PILOT_DISPATCH_DIR` is back to counting an empty queue. `queue.py` is the only
such caller in the tree: every other `DISPATCH_DIR=... request.sh` site is a
selftest fixture or arms.sh with the real dir. The requirement is written at
the gate, in AGENTS.md and in `roles/lane.md`. LOW.
