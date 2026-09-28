# Audit pass 2: PR #533 (lane/thermal507-default)

PR: #533 -- thermal507: PERF_REGIMEN=default, and a pause at the defaults fails the run (#507)
Head verified: 6639d87fa6 (remediation 0184de7e63, merge of origin/master cb85a0b401, NOTES 6639d87fa6).
Pass 1: 2026-09-27-thermal507-default-pass1.md (no HIGH, no MEDIUM; L1-L3).

**Result: clean. None of the pass-1 scenarios can occur on this head except L1, which is accepted as LOW.**

## Scenario by scenario

### L1 (LOW, accepted): the display read adds up to ADB_QUICK_TIMEOUT per call on a wedged adb
Not changed, and it does not need to be. The added wait is at most 20 s per call. `perf_display` runs
in `$(...)`, so its adb failures don't count toward the soak's ADB_FAILURES. Nothing is
mis-scored. It stays as pass 1 filed it.

### L2 (fixed): a firmware whose dumpsys line doesn't match drops `displays` silently
`perf_display` now writes `displays` when `disp or out`, not just when `disp`. So a firmware
whose display line has another shape writes `"displays":{}`, and a run where adb said nothing
writes `{}` with no key at all. The two cases can now be told apart. I pulled the parser out of
soak_title.sh and gave it four inputs:

| input | output |
|---|---|
| nothing (adb silent) | `{}` |
| settings only, no display line | `{"displays":{},...}` |
| settings + a non-AOSP display line | `{"displays":{},...}` |
| settings + an AOSP DisplayInfo line | `{"displays":{"0":"ON"},...}` |

The only thing that reads the key is selftest 99-default-regimen's `display` leg, which reads
`x.get("displays") or {}`. An empty dict does not change that leg's result.

### L3 (fixed): `e0` re-states first_pause's episode filter inline
Now there is one copy of the filter. `thermal_state.first_episode(recs)` returns `(episode, origin)`,
and `first_pause` is built on it. title_verdict.py unpacks `first_episode(therm or [])`, which is
the same input `fp = first_pause(therm or [])` was computed from. `first_pause` returns non-None
exactly when `first_episode` does. `failed_sustained` is true only when `fp is not None`, so the
unpack cannot see None. That removes the IndexError scenario. The failure text and
`first_pause_s` now describe the same episode from the same origin. `first_pause`'s return value
is unchanged: the body moved but the arithmetic did not.

## Verification

- Ran selftest fragments 84-perf-regimen, 99-default-regimen, 99-thermal-pause and
  99-power-per-frame in a local harness on 6639d87fa6: 56 passed, 0 failed.
- The PR is MERGEABLE against origin/master. At the time of this audit, CI (build x2, selftest) on the head was pending. The fold job
  gates on it.
