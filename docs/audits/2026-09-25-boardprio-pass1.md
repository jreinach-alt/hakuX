# Audit pass 1: PR #270 (lane/boardprio) -- board dispatches by expected improvement

Auditor: `[job.cloud]`, 2026-09-25. Head audited: `4ce1968bc2`.
Scope: the diff against `origin/master` -- `docs/testing/jobs/board.sh`
(`board_filter issues` sort, capacity paragraph), `roles/board.md`,
`selftest.d/97-board-priority.sh`, and the lane's `docs/lanes/boardprio/`.

**Verdict: one MEDIUM, three LOW. → `needs-remediation`.**

## What was checked and holds

- `$SELF/..` resolves to `docs/testing/` both in the owner's checkout and in
  `$WORK/board-wt` after the re-exec, and `board_files.py` lives there; the
  worktree fetches `origin/board` (board.sh:299) before the tick's gate, so
  the sort reads the live tracker, not the fold-lagged copy.
- `board_files.load` can raise (missing file, TOML parse error, git absent);
  every path is caught by `except Exception`, and the list is still printed
  with `[tracker unreadable]` on every line. It does not call `sys.exit`, so
  no path empties the capacity list.
- The PR half of `board_filter` is byte-for-byte unchanged in behaviour;
  startability (SKIP / SKIP_PREFIX) is applied before the sort and the
  fixture's lane-held `#299` stays out.
- Tier logic matches the role file and NOTES: game-visible (score desc) →
  score > 0 desc → no estimate → measured zero → no row, oldest first inside
  each. Ties are broken on the issue number, and the fixture puts each tie's
  winner in the middle of three, so first-wins / last-wins mutants cannot pass.
- The fragment runs green here (9/9). The lane's seven mutants and the
  falsification run against master (8 of 9 red, order = gh's) are recorded
  in NOTES; the falsifier is not tautological -- the green leg on master is
  the startability check, which proves the run reached the filter.
- Real tracker (`origin/board`, today): 128 rows, 39 carry the fields, all
  `impact_*` values are TOML integers and `game_visible` is bool; `#77`,
  `#303`, `#311` are game-visible.

## MEDIUM

### M1. A non-integer estimate ranks as a *measured zero* and says so

`board.sh`, `rank()`: `px, one = (v if isinstance(v, int) and not
isinstance(v, bool) else 0 ...)`, then `if "impact_px" in row ...: if score
<= 0: return (3, 0, n), "[impact 0 px, measured]"`.

A float (or a string) in `impact_px` / `impact_onestep_px` is coerced to 0,
and because the field is *present* the row falls into tier 3 -- below every
row with no estimate at all -- with a key that asserts it was measured.

**Failure scenario (reproduced):** a tracker with
`[issue.1] impact_px = 746668.0` and `[issue.2]` with no fields, run through
the real `board_filter` (`HAKUX_BOARD_REF=""`, fixture beside a copy of
`board_files.py`), prints

```
#2 [no impact estimate] no est
#1 [impact 0 px, measured] float est
```

A 746,668-px issue dispatches last and the line tells the board and a human
that it was measured at zero.

**Why this is reachable, not hypothetical:** the diff's own role-file text
tells the board to write `impact_px` as "the size times how tractable the
next step is" -- a product with a fraction, which naturally comes out as a
float (`1493336 * 0.5` is `746668.0`), and a TOML writer emits it as
`746668.0`. Nothing validates these fields (no reader of `impact_px` exists
outside `board.sh` and the fragment). The inline comment says a malformed
value counts as zero "so one bad row must not empty the list" -- that goal is
right, but zero is the wrong substitute here because this change made zero a
*tier* with a meaning.

Blast radius: dispatch order and a false label on the affected rows; no
crash, nothing dropped from the list. Hence MEDIUM, not HIGH.

**Fix (either is fine):** accept any finite real number
(`isinstance(v, (int, float)) and not isinstance(v, bool)`, then `int(v)`),
and send anything else that is present but unusable to its own visible key
(e.g. `[impact unreadable: impact_px='…']`, ranked with the no-estimate tier)
rather than to "measured". Add a fixture row with a float and one with a
string, each in the middle of a tie, so the fragment sees it.

## LOW

### L1. NOTES' top summary still lists four tiers

`docs/lanes/boardprio/NOTES.md`, "What changed" lists tiers 1–4 without the
measured-zero tier; the correction lives only in the appended "Attempt 2"
section. A reader of the summary gets the attempt-1 order. Correct it in
place.

### L2. `fleet.py`'s DISPATCHABLE list keeps a different order

Acknowledged in NOTES ("For the owner / the next lane"). The session-start
FAIL line and the board brief can now list the same issues in two orders.
Not a defect in this diff's files; worth an issue so it is not lost.

### L3. An unrelated rule rides in the dispatch bullet

`roles/board.md`: the host-delegation routing sentence
(`decision-needed` / `regression-accepted` → `[board]` comment to the host)
is inserted mid-way through the "Dispatch up to three lanes" bullet, between
the ordering rule and "For EACH one". It reads as part of the per-issue
procedure. Its own bullet would be clearer; no behaviour depends on it.

## For pass 2

Verify that M1's scenario can no longer occur: run the reproduction above
(float `impact_px` beside an unestimated row) against the remediated head and
check the float row ranks by its value and is not labelled "measured"; and
that a string value neither raises nor reads as a measured zero.
