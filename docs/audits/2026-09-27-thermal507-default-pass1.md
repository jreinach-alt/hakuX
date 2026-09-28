# Audit pass 1: PR #533 (lane/thermal507-default)

PR: #533 -- thermal507: PERF_REGIMEN=default, and a pause at the defaults fails the run (#507)
Head audited: 105db74e3a (the PR's own commit; the rest of the diff is #523's, audited in
2026-09-27-thermal507-power-pass1/pass2).
Files read: docs/testing/soak_title.sh, docs/testing/title_verdict.py,
docs/testing/jobs/selftest.d/99-default-regimen.sh, docs/lanes/thermal507/NOTES.md; and
thermal_state.py (episodes, first_pause, origin, describe) and devices.sh (device_perf_set)
for context.

**Result: no HIGH, no MEDIUM. Three LOWs.**

## What was checked

- **`e0 = [...][0]` cannot IndexError.** It runs only when `failed_sustained` is true, i.e.
  `fp is not None`. `first_pause` returns non-None only when the same filter
  (`before is None or before > origin(ok)`) over `episodes(recs)` is non-empty, and its `ok`
  is the same set as the verdict's `read`. So the list is non-empty whenever it is indexed.
- **MAX is unchanged.** `not at_defaults` gates only the thermal-pause void; `regimen` is
  None for a run with no or unreadable perf_regimen.json, which keeps the old void.
- **`thermal-unread` still voids at the defaults.** `gap` is computed only when there is no
  `hit`, and the `elif gap` branch does not depend on `at_defaults`.
- **The rating candidate is withheld.** `sustained_fail` goes into `fails` (when not void),
  so `v["pass"]` is false and the `rating_candidate` block does not run.
- **The cool-down gate's pause does not fail a default run**: first_pause drops an episode
  whose `before <= origin`. Selftest leg `cooldown` covers it.
- **The regimen writes and restores.** `default` sets PERF_SET=1 and uses device_perf_set, which
  reads back. The exit trap's perf_leave restores REST as for `max`/`rest`.
  The whitelist change means `default` is no longer coerced to MAX.
- **perf_display runs in `$(...)`**, so adb_call's failure accounting can't reach the
  soak's ADB_FAILURES. A parse on empty stdin prints `{}`, and `disp()` maps unparsable
  text to null.
- **Display regexes against the AOSP DisplayInfo shape.** `displayId (\d+)` does not match
  `displayGroupId`. `, state (\w+)` does not match `, committedState`.
- Ran 99-default-regimen (7), 99-thermal-pause (15) and 84-perf-regimen (21) in a
  local harness: 43/43. The branch merges cleanly into origin/master (merge-tree).

## Findings

### L1 (LOW): the end-of-soak display read can add up to ADB_QUICK_TIMEOUT to every run
`soak_title.sh` now makes one more adb call after `soak end` (and one at start in every
regimen, `off` included). On a wedged adb this adds up to 20 s per call to the run's wall
time. Scenario: an adb that hangs at the end of a soak delays the exit by up to 20 s more
than before. The delay is bounded and nothing is mis-scored.

### L2 (LOW): a firmware whose dumpsys line doesn't match drops `displays` silently
If `mBaseDisplayInfo=` doesn't appear, or has a different shape, on the Thor or Nova
firmware, `displays` is absent from `display.start/end`. That reads the same as "no
display lines". The settings keys still show that adb answered, so the case can be told
apart from an adb failure. But no `PERF:` line flags it: a Thor run with its second screen
ON records nothing about it. The PR states this is unverified. Suggest `displays: {}` or a
note when the settings answered but no display line matched. The first `default` soak
should check this either way.

### L3 (LOW): `e0` re-states first_pause's episode filter inline
title_verdict.py now has a second copy of the "not the cool-down's episode" filter. If one
copy changes (e.g. first_pause starts excluding episodes over before the mark) and the other
doesn't, `fp` can be non-None while the inline list is empty: an IndexError in judge(). Or the
failure text can name a different episode than `first_pause_s` does. Returning the episode
from thermal_state, or a shared `run_episodes()`, would leave one copy.

## Routing
Only LOWs: `needs-audit-2`. Pass 2 should confirm that L1-L3 are either addressed or
accepted as LOW, and that selftest CI on the head is green (pending at the time of this
audit).
