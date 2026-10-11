# lane.usagerule1010: usage Low enters only at 80% of the week used AND a projection over 100% (#433, 0.5)

State: ready

Lane: usagerule1010          Issue: none (harness fix dispatched directly by lane.local, #433 umbrella)
Base: master @ b74cff74ed
Files: docs/testing/jobs/usage/mode.sh, docs/testing/jobs/models.toml, docs/testing/jobs/selftest.d/89-usage-mode.sh,
       docs/lanes/usagerule1010/NOTES.md, docs/lanes/usagerule1010/PR.md
Prediction: none: harness only, no pixels
Needs device: no    Needs NDK: no
Release note (none): harness

Owner, 2026-10-10 ~10:30 PDT, after the project entered Low at 19% of the week used on 10-10 09:30 PDT (a hot
6h-trailing-rate projection of 134%, nothing else): "I do not want low enabled at all this weekend. Bad call
there. It only should trigger when we're at 80 percent for the week and projected to go over 100."

## Before / after

- **Before**: enter Low when `estimated% >= 80` **OR** `projected-at-reset% >= 90`; back to Normal when
  `estimated% < 80` **AND** `projected-at-reset% < 75`.
- **After**: enter Low when `estimated% >= 80` **AND** `projected-at-reset% > 100` (strict: "go over"); back to
  Normal when `estimated% < 80` **OR** `projected-at-reset% < 95`.

`models.toml`'s `[usage]` table: `low_pct` unchanged at 80; `low_proj` 90 -> 100; `normal_proj` 75 -> 95 (keeps
the hysteresis purpose -- a Low that just started doesn't flap on one quiet hour -- re-anchored under the new
`low_proj`; the gap itself shrinks from 15 points to 5, per the brief's own numbers, not a choice this lane made).
Both files' comments spell AND/OR in words, and the printed switch reason names both numbers and both lines,
e.g. `85% used >= 80 and 101% projected > 100`.

## Files changed

- `docs/testing/jobs/usage/mode.sh`: header "WHEN" block restates the rule with the owner's 10-10 quote, drops
  the old 90/75 sentence; `evaluate()`'s python block replaces the single `or`-chain with explicit `entering`
  (AND) / `leaving` (OR) booleans and picks the printed reason from those plus the current mode.
- `docs/testing/jobs/models.toml`: `[usage]` table defaults and comments (see above). No other table touched.
- `docs/testing/jobs/selftest.d/89-usage-mode.sh`: top-of-file one-line summary updated; the whole "every tick"
  block rewritten for the new rule (see cases below).
- Grepped `docs/testing` and `AGENTS.md` for `low_proj|normal_proj|USAGE_LOW|projected`: no other live doc states
  the old rule (`AGENTS.md` has no usage-Low section at all; the only other hits are inside other lanes' own
  historical `PR.md`/`NOTES.md` files -- `usagemode1009`, `usage24h1009`, `modelpolicy1010` -- which are frozen
  records of what was true when each was written, not live documentation, and are outside this lane's territory).

## Test cases (`SELFTEST_ONLY=89-usage-mode bash docs/testing/jobs/selftest.sh`: 56 passed, 0 failed)

| estimated% | projected% | starting mode | result | demonstrates |
|---|---|---|---|---|
| 85 | 101 | normal (after `auto`) | low | both lines true; switch log names both numbers |
| 85 (unchanged) | 101 (unchanged) | low | low (hold) | a tick that changes nothing logs nothing |
| 85 | 97 | low | low | hysteresis: not yet under `normal_proj` (95) |
| 85 | 94 | low | normal | OR on the way out: projection alone clears it |
| 40 | 95 | normal | normal | pct alone can't enter even near the projection line |
| 19 | 134 | normal | normal | **today's case** -- projection alone is not a reason |
| 85 | 100 | normal | normal | projection line is strict: "over", not "at or over" |
| 85 | 101 | normal | low | both lines true (re-confirms the entry line) |
| 10 | 50 | low | normal | no latch, both lines clear |
| 2 | (none) | normal | normal | week rollover, no projection yet |
| 85 | 65 (dial `low_proj=60`) | normal | low | the projection half of the entry line is still a `models.toml` dial, pct held >= 80 |
| 85 | 97 (low-active deleted by hand) | low | low, file recreated | heal: inconsistent state repairs on the next tick |

## Mutants (both required by the brief)

Applied by hand to a scratch-restored copy of `mode.sh`'s `entering` line (`git diff` confirmed clean after each
revert):

1. `pct >= low_pct and p > low_proj` -> `pct >= low_pct or p > low_proj` (reinstate OR on the entry line):
   **2 checks fail** -- "19% used, 134% projected stays normal" (the case the owner called out by name) and
   "85% used, 100% projected stays normal" (OR lets `pct >= low_pct` alone trigger Low here too).
2. `p > low_proj` -> `p >= low_proj` (reinstate non-strict): **1 check fails** -- "85% used, 100% projected stays
   normal" (the owner's word was "over", not "at or over").

Neither mutant survives; the suite is not vacuously passing.

## Full suite

`docs/testing/jobs/selftest.sh` (whole, no `SELFTEST_ONLY`): **3255 passed, 0 failed, all 131 fragments** --
no regression outside fragment 89 from this change.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
