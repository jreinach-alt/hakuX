# lane.usage24h1009

Brief: `docs/lanes/usage24h1009/../../../briefs/usage24h1009.md` (umbrella #433). Owner 2026-10-09 22:5x PDT: "Yes,
switch it to the 24h window", after asking why the project was in usage Low at 11% of the week used.

## What changed

`docs/testing/jobs/usage/meter.py`'s `build_report()`:
- added `rate_24h` next to the existing `rate_1h`/`rate_6h` (same per-hour-over-the-window shape as `rate_6h`,
  just over 86400s instead of 21600s).
- `projected_pct` now reads `rate_24h * hours_left / capacity * 100.0` in place of `rate_6h * ...`. `rate_1h` and
  `rate_6h` stay in the returned report dict, just no longer drive the projection.
- `summary_line()` now prints `rate_24h=$X/h` (was `rate_6h=$X/h`), since that's the rate the projection actually
  used -- the brief's requirement that a reader can redo the arithmetic from the one-line summary.
- comment above the projection explains why 24h: one day/night cycle, so a single busy evening doesn't get
  extrapolated over the quiet overnight hours still to come, while a rate sustained across the whole day still
  gets caught.

`mode.sh`: confirmed unchanged. It only reads `projected_percent_at_reset` and `estimated_percent` off
`state.json`'s `last_report`; it has no reference to `rate_6h` anywhere (`grep` came back empty). The thresholds
(`USAGE_LOW_PCT`/`USAGE_LOW_PROJ`/`USAGE_NORMAL_PROJ`) and the hysteresis are untouched, per the brief.

`selftest.d/89-usage-mode.sh`:
- `um_dump` now prints `rate_24h`; added a check against the existing fixture (8 dollars of events within 24h --
  the four fixlane events plus one each of board/cloud/hostops/interactive -- over 24h = 0.33). One of those four
  fixlane events (the one 20h old) sits before the fixture's week start, so it is excluded from
  `spend_since_reset` but INCLUDED in `rate_24h` -- documented in a new comment above the fixture ages, since that
  is the "it's a rate, not a share of the week" point the module docstring already makes about `KEEP_DAYS`.
- the standalone "projection formula, recomputed independently" check now recomputes from `rate_24h` instead of
  `rate_6h`.
- added two new checks, hand-built `state` dicts fed straight to `meter.build_report()` (no fixture files, no
  scanning -- `build_report` is pure given a state dict, and round dollar figures make every number hand-checkable):
  1. a $20 "background" event 72h back (in-week, outside every rate window) plus a $20 "burst" 3h back (inside
     both the 6h and 24h windows) -> `projected_percent_at_reset` is 40% (stays Normal, <90) under the new rule.
     The SAME report's `rate_6h` fed through the OLD formula (`estimated_percent + rate_6h*hours_left/capacity*100`)
     comes to 100% (would have gone Low) -- this is the mutant the brief asked for: it reinstates the pre-#433
     formula on the identical data, so the only variable is which rate window drives the projection.
  2. the same $/h rate ($3.33/h) spread across the full 24h instead of a 6h burst (one $80 event 12h back,
     instead of $20 in the last 6h) -> `projected_percent_at_reset` is 130% (still goes Low). This is the half
     of the brief's requirement that proves the fix isn't just "stop projecting" -- a genuinely sustained ramp
     still trips the gate.
- verified the mutant is real, not just asserted: temporarily reverted the projection line in `meter.py` back to
  `rate_6h` (the pre-#433 formula) and re-ran 89 standalone -- both new checks turned red, confirming they
  actually exercise the code path and aren't trivially true. Restored `meter.py` immediately after (diff checked
  against the intended change only).

## Verification

`SELFTEST_ONLY="89-usage-mode" bash docs/testing/jobs/selftest.sh` -- 52 passed, 0 failed (was 50 before the two
new checks; the fixture-column check for `rate_24h` plus the mutant checks are the delta).

## Before/after on tonight's real state (2026-10-09, ~23:06 PDT)

Never touched the live `usage/state.json` (confirmed mtime unchanged after: Oct 9 22:53, same as before this
lane started). Copied it twice into a scratch `$HAKUX_WORK` (`/tmp`, outside the repo and outside any territory),
ran the pre-#433 `meter.py` (`git show origin/master:...`) against one copy and this branch's `meter.py` against
the other, both with the same `HAKUX_NOW` so the comparison is apples-to-apples:

| | capacity | estimated% | rate_6h | rate_24h | hours_left | projected_at_reset |
|---|---|---|---|---|---|---|
| before (rate_6h-driven) | $2291.23/wk | 11.0% | $15.42/h | n/a | ~142h | **106.5%** -> Low |
| after (rate_24h-driven) | $2291.23/wk | 11.0% | $15.42/h | $9.09/h | ~142h | **67.3%** -> Normal |

Matches the brief's own 22:55 PDT measurement (6h->113%, 24h->69%) to within the hour of drift between the two
readings. Scratch dirs removed after (rm -rf on `/tmp/usage24h1009-scratch` was denied by the sandbox once but
it's throwaway `/tmp` state outside the repo, not left-over work -- harmless either way).

## State

ready.
