# Fix the 10-19 11:14 master-red: a usage-meter time bomb and a hold-tiers clock race

State: ready

Lane: masterred-verdict1019   Issue: #433
Base: master @ 913e1524ffc3e3023144bdc1f8b77aeafdd75f38
Files: docs/testing/jobs/usage/meter.py, docs/testing/jobs/selftest.d/88-usage-meterfit.sh, docs/testing/jobs/selftest.d/99-hold-tiers.sh, docs/lanes/masterred-verdict1019/NOTES.md, docs/lanes/masterred-verdict1019/PR.md
Prediction: none: testing-harness fix, no pixels/perf claim, no device time
Needs device: no    Needs NDK: no

Master went selftest-red at 2026-10-19 11:14 for two unrelated reasons, in
shards 1 and 2 of the 4-shard host run (shard 3/4, the one named in the jam
title, actually passed -- see below and NOTES.md item 3).

1. `docs/testing/jobs/usage/meter.py`'s `collect_fit_samples()` cut off at
   real `time.time() - 14d`, ignoring the `88-usage-meterfit.sh` fixture's
   pinned `UF_NOW`. The fixture's 5-day-old sample crossed that real
   cutoff 9 real days after `UF_NOW`'s calendar date (2026-10-19 10:40
   PDT) and silently dropped out, collapsing the fallback fit. Fix: thread
   an explicit `now=None` parameter through `collect_fit_samples` (and
   have `combined_price_map` actually pass its own `now` through, which it
   wasn't) so the fixture's pinned clock is honoured; `fit_prices()` is
   untouched (no fixture caller crosses its edge, real callers still want
   wall-clock). Added a falsifier whose own fixture clock is pinned 30
   real days in the past (computed at run time, not a fixed calendar
   date), so this doesn't quietly start failing again next week the way
   the original case 2 just did; paired MUTANT check confirms it fails
   without the fix.

2. `docs/testing/jobs/selftest.d/99-hold-tiers.sh` leg (c) read `date +%s`
   once to name a "59s old" and a "61s old" request against
   `HOLD_YIELD_S=60`, then `yield-check` read the clock again -- a loaded
   4-shard run can lose that race by more than 1s. Fix: widen the margins
   to 30s/90s (HOLD_YIELD_S unchanged at 60).

3. The jam title itself (`master-red:99-verdict-10min.sh`, the last
   fragment printed by the one shard that passed) comes from
   `/home/justin/hakux-work/offline-git/master_health_check.sh` --
   host-side, outside this git repository, no lane can PR it. Found it
   already fixed independently on the host (dated backup
   `master_health_check.sh.bak-20261019-fragattr`, the new code's own
   comment names this exact incident) before this lane started; replayed
   its new attribution logic by hand against the real
   `fold-logs/master-health-20261019T1114-913e1524ff.log` and confirmed it
   now produces `88-usage-meterfit.sh,99-hold-tiers.sh` -- the correct
   pair. No action needed from this lane; full account in NOTES.md.

Verification: `SELFTEST_ONLY="88-usage-meterfit.sh"` (15/15) and
`SELFTEST_ONLY="99-hold-tiers.sh"` (35/35) both green alone; full
`SELFTEST_SHARD=0/4` (290/290) and `SELFTEST_SHARD=1/4` (1267/1267) --
shards 1 and 2, the ones that were red -- both ran to completion green, no
FAIL lines in either log. `origin/master` merged in after both shard runs
started (clean, no files the shards touch).

Release note (none): testing-harness infrastructure, not emulator code.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
