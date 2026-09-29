# Audit pass 2: lane.fgunknown (PR #593, issue #592)

Head verified: `598f880b95` (the code commit `3c3c0bfd5c` plus the pass-1
file). No remediation commit: pass 1 raised no HIGH and no MEDIUM, only two
LOWs, and neither asked for a code change.

**Verdict: clean. No HIGH or MEDIUM open; both LOWs stand as written and
are not blocking. fold-ready.**

## Pass-1 findings

### L1 (LOW): non-adjacent unknowns abort as "two in a row" -- still present, accepted

`soak_title.sh` fg_watch still leaves `unk` untouched in the rc 3 branch, so
in front, unknown, unreadable, unreadable, unknown still aborts at `(2/2)`.
The scenario can still occur. It fails safe (abort, never play on an
unconfirmed focus), the block comment says "it neither adds to nor clears
the unknown count", and pass 1 graded it quality only. Not a blocker.

### L2 (LOW): "about 60 s" is the typical bound, not the worst -- still present, accepted

The comment still says "about 60 s". The worst case is still `timeout -k 5`
(15 s per read against an adb that ignores TERM), which gives roughly 85 s.
That is a precision point about the comment. The behaviour is bounded
either way: `FG_UNREADABLE_MAX` counts reads, not seconds. Not a blocker.

## Re-checked on the head

- `hakux_in_front` (`devices.sh:471`): `rc=$?` now reads `adb_call`'s own
  exit code, because the `tr` moved out of the substitution. Exit 124 goes
  to "adb hung", any other non-zero to "adb failed", and a whitespace-only
  answer to "answered nothing". All three return 3. The awk's 0/1/2 are
  unchanged.
- Callers of `hakux_in_front`: there are three, all in `soak_title.sh`, and
  no caller outside it. `fg_wait` (798) breaks only on rc 0. The USB-dialog
  BACK stays gated on rc 1. After the remedy, rc 3 aborts with
  `not-foreground: unreadable (...)`. `fg_watch` (840) plays on rc 0 only.
  The end-of-hold split (972) reads rc 0 only as render-black, so rc 3 reads
  as display-black.
- `fg_abort` on the new line yields `ROUTE ABORTED: not foreground
  (unreadable)`. `title_verdict.py:291` matches the anchored
  `^not-foreground: ` line and voids the run. The `FOREGROUND:
  foreground-unreadable:` progress lines do not match it.
- Ran `SELFTEST_ONLY="99-fg-unreadable 99-display-covered"
  docs/testing/jobs/selftest.sh` on the host against `598f880b95`: 32
  passed, 0 failed.
- CI on the head: build x2 and selftest 0-3 all pass.
