# lane.usage24h1009: project the week's usage from the trailing 24h burn rate, not the trailing 6h (#433)

State: ready

Lane: usage24h1009          Issue: none (harness fix dispatched directly by lane.local, #433 umbrella)
Base: master @ 39379dafdd
Files: docs/testing/jobs/usage/meter.py, docs/testing/jobs/selftest.d/89-usage-mode.sh, docs/lanes/usage24h1009/NOTES.md, docs/lanes/usage24h1009/PR.md
Prediction: none: no arm (meter/selftest change, no device, no pixels)
Needs device: no    Needs NDK: no
Release note (none): harness-internal (usage meter / selftest), not emulator code.

Owner 2026-10-09 22:5x PDT, after asking why the project was in usage Low at 11% of the week: "Yes, switch it to
the 24h window."

**The defect** (measured 10-09 by lane.local): `meter.py`'s projection extrapolated the trailing 6h burn rate
over every remaining hour of the week, nights included, so Low/Normal followed how busy the last six hours were,
not the week. A 15:00-18:00 burst (two Opus lanes + an interactive session) pushed the projection from 21.9% at
14:01 PDT to 90.7% at 18:04 PDT four hours later, on a week that was 7% used.

**The fix**: `build_report()` now computes `rate_24h` the same way it already computed `rate_6h` (per-hour,
over the window) and projects from that instead. `rate_1h`/`rate_6h` stay in the report for visibility;
`summary_line()` prints whichever rate drives the projection (`rate_24h=$X/h`) so the arithmetic is redoable
from the one-line summary. `mode.sh` needed no change -- confirmed by grep, it reads only
`projected_percent_at_reset`/`estimated_percent`, never a rate directly.

**Before/after on tonight's real `usage/state.json`** (copied to a scratch `$HAKUX_WORK`, live file never
written -- mtime unchanged across the whole lane):

| | rate_6h | rate_24h | hours_left | projected_at_reset |
|---|---|---|---|---|
| before (old formula, projects from rate_6h) | $15.42/h | n/a | ~142h | **106.5%** -> Low |
| after (this change, projects from rate_24h) | $15.42/h | $9.09/h | ~142h | **67.3%** -> Normal |

Matches the brief's own 22:55 PDT reading (6h->113%, 24h->69%) within the hour of drift between the two.

**Tests** (`selftest.d/89-usage-mode.sh`): moved the existing rate/projection checks onto `rate_24h`; added a
`rate_24h` fixture check (0.33, including a fixlane event 20h back that is before the fixture's week start but
still inside the 24h rate window -- a rate is wall-clock, not week-relative, same point the module docstring
already makes about `KEEP_DAYS`). Added two hand-built-`state` checks: a 6h burst after 18h quiet stays Normal
under the new rule (40% projected) while the OLD rule on the identical report would have gone Low (100%
projected) -- that's the mutant, reinstating the pre-#433 formula rather than deleting the projection outright;
and the same $/h rate sustained across the full 24h still goes Low (130% projected), proving the fix doesn't
just suppress the gate. Verified the mutant is live by reverting the projection line in a scratch copy and
re-running 89: both new checks turned red, then reverted.
`SELFTEST_ONLY="89-usage-mode" bash docs/testing/jobs/selftest.sh`: 52 passed, 0 failed.

No GitHub, no board-file edits, no device time -- as scoped. `host-tools/usage_meter.py` (stale 10-02 copy, not
run by anything) left untouched.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
