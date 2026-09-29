# Audit pass 1: lane.fgunknown (PR #593, issue #592)

Head audited: `3c3c0bfd5c` (one commit on master `2c950e0a1e`). Diff read:
`docs/testing/devices.sh`, `docs/testing/soak_title.sh`,
`docs/testing/jobs/selftest.d/99-fg-unreadable.sh` (new),
`docs/testing/jobs/selftest.d/99-display-covered.sh`,
`docs/lanes/fgunknown/NOTES.md`. CI on the head: build x2 and selftest 0-3
all pass.

**Verdict: no HIGH, no MEDIUM. Two LOWs.**

## What was checked

- **`hakux_in_front` exit codes.** `adb_call` maps both 124 and 137 to 124
  and returns the last attempt's rc after its one retry (`ADB_RETRIES=1`), so
  rc 124 -> "adb hung", any other non-zero -> "adb failed (exit N)", rc 0
  with only whitespace -> "answered nothing", all exit 3. The remote command
  ends `; true`, so a device that answered returns 0 and reaches the awk,
  whose exits 0/1/2 are unchanged. `out` and `rc` are declared `local`
  before the assignment, so `$?` is the substitution's, not `local`'s.
- **Every caller of `hakux_in_front`.** Three, all in `soak_title.sh`:
  - `fg_wait` (before input): returns 0 only on rc 0; the USB-dialog BACK is
    gated on rc 1; rc 2 and 3 both wait, get one `am start` remedy, and
    abort with the right `not-foreground: unknown|unreadable` line. rc 1
    keeps the raw `not-foreground:` line as before.
  - `fg_watch` (during the route): rc 3 counts `unr` and aborts at
    `FG_UNREADABLE_MAX`; rc 2 resets `unr`, counts `unk`, aborts at 2; rc 0
    resets both; rc 1 (and any other rc) falls through to the kill, as on
    master. No path treats 2 or 3 as in front.
  - the end-of-hold render/display-black split: tests `rc = 0` only, so
    rc 3 reads as display-black, same as unknown. Correct.
- **Log consumers.** `title_verdict.py:291` voids on `^not-foreground: `;
  the new `not-foreground: unreadable (...)` line matches it, and the
  `FOREGROUND: foreground-unreadable: ...` progress lines do not (anchored).
  No other script keys on `foreground-unknown`.
- **Tests.** 99-fg-unreadable's fake adb `exec sleep 30` under
  `ADB_QUICK_TIMEOUT=1` yields rc 124 through the real `adb_call`; FAIL
  yields exit 1 twice (retry exercised). Legs (a), (c), (d-bound), (f) fail
  on master's code as the PR table says; (b), (d-unknown), (e) pin the
  unchanged rules. The `silent` leg of 99-display-covered is updated to the
  new line rather than deleted.

## Findings

### L1 (LOW): non-adjacent unknowns abort as "two in a row"

`soak_title.sh` fg_watch: the rc 3 branch leaves `unk` untouched, so
in front, unknown, unreadable, unreadable, unknown aborts with
`FOREGROUND: ... (2/2)` and `not-foreground: unknown`, though the two
unknowns were separated by two unreadable reads. This is the conservative
direction (it aborts, it never plays blind) and the block comment states
"it neither adds to nor clears the unknown count", but the one-line rule
at the top of the comment ("two unknowns in a row") no longer describes it.
Quality only; no fix required beyond wording, if any.

### L2 (LOW): the "about 60 s" bound is the typical case, not the worst

`adb_call` runs `timeout -k 5`, so a read whose adb ignores TERM takes 15 s,
and a failed-then-hung read takes 2 s + 10 s. Five in a row can therefore
run to roughly 85 s of route input on an unconfirmed focus, not 60 s. The
issue asked for "about 60 s" and real adb exits on TERM, so this is a
comment precision point, not a behaviour defect.

## Nothing else

No correctness, safety or crash-path defect found in the diff.
