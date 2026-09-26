# Audit pass 2: PR #270 (lane/boardprio) -- board dispatches by expected improvement

Auditor: `[job.cloud]`, 2026-09-25. Head audited: `54aeec62d8`
(remediation of pass 1, `docs/audits/2026-09-25-boardprio-pass1.md`).

**Verdict: clean. M1 can no longer occur; L1 and L3 are fixed; two new LOWs.
→ `fold-ready`.**

## M1 -- a non-integer estimate ranked as a measured zero: CANNOT OCCUR

`rank()` in `board.sh` now reads each impact field as a finite int or float
(`isinstance(v, (int, float)) and not bool and math.isfinite(v)`) by its
integer part; any other present value is collected in `bad` and the row
returns `(2, 0, n), "[impact unreadable: <field>=<repr>]"` -- the
no-estimate tier -- before the measured-zero branch is reached. The
measured-zero branch is now reachable only when every present value is a
finite number and the score is `<= 0`.

Pass 1's reproduction, re-run against the remediated `board_filter`
(extracted from `board.sh` at `54aeec62d8`, `HAKUX_BOARD_REF=""`, tracker
beside a copy of `board_files.py`), extended with the other shapes a writer
could produce:

```
#6 [impact 9,223,372,036,854,775,807 px] huge int      impact_px = 2^63-1
#1 [impact 746,668 px] float est                       impact_px = 746668.0
#2 [no impact estimate] no est
#3 [impact unreadable: impact_px='746668'] string est
#4 [impact unreadable: impact_px=inf] inf
#5 [impact unreadable: impact_onestep_px='x'] mixed    impact_px = 5000
#7 [impact 0 px, measured] neg float                   impact_px = -3.5
#9 [impact 0 px, measured] measured zero               impact_px = 0
#8 [no tracker row] norow
exit=0
```

- The float `746668.0` ranks by its value above the unestimated row and is
  not labelled measured (pass 1 printed it last as `[impact 0 px, measured]`).
- A string and an `inf` neither raise nor read as measured; both sit in the
  no-estimate tier and name the offending field.
- A 64-bit maximum int does not overflow `math.isfinite`; nothing empties
  the list.
- The fragment `97-board-priority.sh` now carries a float (`#310`), a string
  (`#290`) and a nan (`#304`), each in the middle of a three-way tie, with a
  check that names each one's key; a first-wins or last-wins mutant still
  cannot pass. CI's `selftest` job passed on `54aeec62d8` (run 36200909109).

## L1 -- NOTES summary listed four tiers: FIXED

`docs/lanes/boardprio/NOTES.md` "What changed" now lists all five tiers,
including the measured zero below the unestimated rows and the unreadable
case ranked with them, in place (not appended).

## L2 -- fleet.py's DISPATCHABLE order differs: UNCHANGED (as expected)

Outside this diff's files; still acknowledged in NOTES. Not a blocker.

## L3 -- routing rule inside the dispatch bullet: FIXED

`roles/board.md`: the host-delegation sentence is now its own bullet after
"Dispatch up to three lanes"; the dispatch bullet also gained "write impact
values as numbers (int or float)".

## New LOWs (no blocker)

### N1. A row with one good and one unreadable field loses the good one

`impact_px = 5000, impact_onestep_px = "x"` ranks with the unestimated rows
(`#5` above) although 5,000 px is known. The label is truthful and names
the bad field, so the board sees it and can fix the row; bounded to order
only. Ranking by the readable part with the unreadable field still named
would be more faithful.

### N2. `board.sh`'s header comment above `board_filter` omits the unreadable case

The tier list at `board.sh` ~l.100 still says tier 3 is "a row with no
impact fields"; the code (and NOTES, and the role file) also rank an
unreadable value there. Comment only.

A negative float (`-3.5`) reads as a measured zero, as a negative int did
before this change; a negative estimate is itself a writer error and is not
new with the remediation, so it is not raised.
