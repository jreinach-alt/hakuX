# Audit pass 1: PR #514, lane focusanr (#513)

Head audited: `ea20bdd7b7`. Diff: `docs/testing/devices.sh` (the awk in
`hakux_in_front`), `docs/testing/jobs/selftest.d/99-display-covered.sh` (two
ANR legs and a mutant), `docs/lanes/focusanr/NOTES.md`.

**Verdict: no HIGH, no MEDIUM, no LOW. Nothing for pass 2 to verify: fold-ready.**

## What was checked

1. **Block order and the stop anchor.** AOSP `InputDispatcher::dump` prints
   `Input Dispatcher State:` and the live state, then, if `mLastAnrState` is
   non-empty, `Input Dispatcher State at time of last ANR:` at column 0. The
   `onAnrLocked` path builds `mLastAnrState` as `INDENT "ANR:"` (two spaces),
   then Time/Reason/Window at four, then a full `dumpDispatchStateLocked`.
   The adb-side grep (`^  [A-Za-z][A-Za-z]*:`) keeps `  ANR:` and drops the
   header, so the awk's `/^  ANR:/` stop is the first surviving line of the ANR
   block. The fallback stop (a second `FocusedDisplayId:` once `fd` is set)
   covers a layout without `  ANR:`. The stop is placed before the section and
   `FocusedDisplayId` rules, so no line from the ANR block reaches `app[]`,
   `win[]` or `fd`.
2. **Unchanged exits.** Nothing in `END` changed. With no ANR block, neither
   stop fires, so every existing leg (Lime3DS, display 4 focus, shade, no
   window, ours, silent) reads exactly as before. The fragment still asserts
   those legs.
3. **Which way an early stop fails.** Suppose some section printed before the
   dispatcher had a two-space `ANR:` line. The read would stop before
   `FocusedDisplayId` and return rc 2 `foreground-unknown`, which is never
   `in-front`. No such section exists in the reader, blocker or processor
   dumps, so there is no failure scenario here. This is recorded as a fact,
   not a finding.
4. **Fixtures.** `fg_anr` emits the live block, then `  ANR:`, the 4-space
   Time/Reason/Window lines, then a second `fg_fix` block without its header
   (`sed 1d`). That matches the real layout the PR body quotes (live
   `FocusedDisplayId` at line 597, the ANR's at 821). The fake adb serves the
   text without the grep, so the 4-space lines are exercised too. They match
   neither the section rule nor the `displayId=N, name='` rule.
5. **Mutant.** Deleting `stop { next }` leaves the `stop = 1; next` line
   dropping only the `  ANR:` line itself, so the ANR block's values overwrite
   the live ones. The `case` pattern requires both legs to fail, each in the
   direction a last-value read produces, so an inert mutant cannot pass it.
   The anchor check is `count == 1`, which exits 3 if the mutant is gone.
6. **Siblings.** Every `dumpsys input` reader on master was grepped. The other
   parser, `docs/lanes/gta482/focus.py`, takes the *first*
   `FocusedDisplayId` (`disp is None`) and the first `FocusedWindows` entry
   per display (`setdefault`), so it already reads the live block. It does
   not carry this bug.
7. **Gates.** CI on `ea20bdd7`: build SUCCESS (x2), selftest SUCCESS. The PR
   is MERGEABLE. The one local selftest failure the PR body names
   (`92-arms-skip-told`) is in `arms.sh`, which does not source `devices.sh`,
   and it passes in CI on the same sha.

## Findings

None.
