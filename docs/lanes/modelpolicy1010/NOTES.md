# lane.modelpolicy1010 -- one model table, one reader, one Low switch (#433, 0.5)

Owner-approved design (2026-10-10, "Proceed with all this."). See
`/home/justin/hakux-work/briefs/modelpolicy1010.md` for the full brief and
the owner-approved table.

## What landed

- `docs/testing/jobs/models.toml`: the one table. `[models]` names the three
  ids and the escalation ladder (haiku -> sonnet -> opus, Fable retired);
  `[kinds.*]` is one row per kind of work with its Normal and Low model;
  `[usage]` holds the four thresholds that used to live in `$WORK/limits.env`
  (`low_pct`, `low_proj`, `normal_proj`, `low_lane_max`).
- `docs/testing/jobs/models.py` / `models.sh`: the one reader. `model_for`,
  `resolve` (kind name OR a bare legacy model id), `dial`, `ladder_step`,
  `cap_at_sonnet`, `is_low`. `$HAKUX_MODELS_TOML` lets a selftest point it at
  a scratch table without touching the real one.
- `docs/testing/jobs/models.env` deleted.
- Every caller the brief named now asks the helper: `lane.sh` (next_attempt,
  token from `$WORK/briefs/<lane>.model` or the "engineering" default),
  `cloud.sh` (the `audit` kind), `ops/ops_tick.py` (the `bookkeeping` kind),
  `titles/pathfind.py` (the `pathfind` kind, FAST=STRONG now that both read
  the same row), `titles/drive.py` (the `drive` kind).
- `docs/testing/jobs/usage/mode.sh`: no longer writes
  `PATHFIND_MODEL_CALLS_MAX` into `limits.env` (see "the dead cap" below);
  `evaluate()` reads its three thresholds via `models.sh dial <name>` instead
  of `limits.env`.

## The dead cap (brief item 6): deleted, not wired

`PATHFIND_MODEL_CALLS_MAX` had no reader anywhere in the repo or host-tools
before this lane (grep-confirmed twice, matching the brief's own claim) --
`pathfind.py`'s navigation agent never consulted a call cap at all. Wiring a
dead dial to something that still does nothing would have been worse than
deleting it: it would have looked like a real Low-mode behavior to the next
person reading `models.toml`. Deleted from `mode.sh`'s `apply_low`/
`apply_normal`; no cap of this kind exists in `models.toml`.

## A ninth caller the brief's inventory missed: `run-claude-job.sh`

The brief's inventory (items 1-8) did not name `docs/testing/jobs/
run-claude-job.sh`, but it sources `jobs/models.env` directly (`. "$JOBS/
models.env"`) and used `MODEL_AUDIT`/`MODEL_BOOKKEEPING` to choose the
`--model` flag for every scheduled job (board tick, audits, hostops-via-
board, everything `board.sh` or a timer invokes through it). Deleting
`models.env` without fixing this left it **broken outright**: under `set -u`,
`"${HAKUX_MODEL:-$MODEL_AUDIT}"` with both unset is an unbound-variable error
that aborts the script before `claude` is even invoked. This is not a
`[ -f ... ] &&`-guarded read like the other four below; the `.` is
unconditional. Fixed in this lane (same shape as `cloud.sh`'s own fix):
reads the `audit`/`bookkeeping` kind through `models.sh`, `HAKUX_MODEL` still
wins. `docs/testing/jobs/run-claude-job.sh` is outside the brief's stated
territory list, but leaving the harness's one job-runner broken was not an
option -- this is a direct, mechanical consequence of deleting `models.env`,
not a design choice that needed the owner's sign-off.

## Four more callers found, left alone: they degrade gracefully

Grepping the whole repo (not just the brief's inventory) for `models.env`/
`MODEL_LANE`/`MODEL_AUDIT`/`MODEL_BOOKKEEPING` after the deletion turned up
four more readers, none of them a hard break:

- `docs/testing/jobs/fold.sh:526` and `docs/testing/jobs/handback.sh:559-560`
  each try to read `LANE_MAX_ATTEMPTS`/`PARK_MAX_ATTEMPTS` out of
  `models.env` via a `sed`/subshell that is itself `2>/dev/null`-guarded, and
  both already fall through to a hardcoded default (`4`) on the next line
  regardless of whether the read succeeded. The `models.env` read is now
  dead code, not broken code -- it always returns empty and the `${VAR:-4}`
  default is what actually runs, same as before this lane on any host where
  `models.env` never set `LANE_MAX_ATTEMPTS` in the first place (it never
  did -- that var was never one of `models.env`'s four).
- `docs/testing/jobs/board.sh:351`'s `positive_gate()` guards the source with
  `[ -f "$SELF/models.env" ] && . ...`; since the file is gone, this is
  simply skipped, and `LANE_MAX=2` (set immediately above) is what the gate
  uses -- matching `lane.sh`'s own no-override default.
- `docs/testing/jobs/status.sh:55` sources `models.env` with `2>/dev/null`,
  and every place that reads `MODEL_LANE`/`MODEL_LANE_ESCALATED` does so as
  `${MODEL_LANE:-opus}` / `${MODEL_LANE_ESCALATED:-fable}` -- a literal
  fallback, not a reference to another unset variable, so `set -u` does not
  trip. The page still renders; it is **cosmetically stale**, always showing
  the hardcoded labels "opus" and "fable" (the old escalation model, now
  retired) in its lane table and footnote instead of a real answer from
  `models.toml`. Worth a follow-up (see PR.md) but `status.sh` is not on this
  lane's territory list and nothing it does is wrong enough to justify
  stepping outside it for a display string.

Ran the fragments covering all four files that reference `models.env`
outside my territory (`78-sweep-remote.sh`, `99-handback.sh`,
`99-limits-env.sh`, `98-lane-shape.sh`, `98-audit-outlet.sh`,
`99-handback-waiter.sh`): 269 passed, 0 failed. None of them assert a value
that depended on `models.env` actually existing.

## A fixture ordering bug this lane's own change surfaced

`selftest.d/89-usage-mode.sh` exports `HAKUX_WORK` (twice, for two different
scratch trees) and never unsets it -- harmless while every reader downstream
of it keeps setting its own `HAKUX_WORK` explicitly. `99-lane-model-file.sh`'s
new `$lm_default` line (`bash "$HERE/models.sh" model engineering`, added by
this lane to replace a literal sourced from the deleted `models.env`) does
not scope `HAKUX_WORK`, so when fragments run in the same shell (sourced, as
`selftest.sh` runs them, exactly how the real fold does it) `lm_default`
silently read 89's leftover `low-active` file and computed Sonnet instead of
Opus for "Normal, engineering" -- two checks failed only when both fragments
ran together, never when either ran alone. Fixed both sides: `89` now unsets
`HAKUX_WORK`/`HAKUX_CLAUDE_PROJECTS`/`HAKUX_SYSTEMD_USER_DIR` at its end (the
same hygiene it already uses for `HAKUX_NOW`), and `99`'s `$lm_default` pins
its own `HAKUX_WORK="$LM/work"` so it does not depend on fragment order at
all. Caught by running touched fragments TOGETHER, not just individually --
worth remembering for any future fragment that computes something at
top-of-file without its own `HAKUX_WORK`.

## Selftests (brief item 7)

- `99-lane-model-file.sh`: all four `lane.sh` mutants rewritten to match
  `next_attempt()`'s current shape (`token`/`resolve()`, no more
  `MODEL_LANE`/`MODEL_LANE_ESCALATED` literals). A new `lm_pymutant()`
  mutates a scratch copy of `models.py` (plus the real `models.toml`) and
  redirects only `lane.sh`'s copy's `MODELS=` line at it -- preserving `$JOBS`
  so `window.sh`/`remote-lane.sh`/`board_files.py` resolve for real, the same
  "mutate one file, not the whole jobs/ tree" lesson the existing
  `lm_mutant()` comment already documents. The old "AUDITS SIZED TO THE DIFF"
  cloud.sh special case and its selftest section were removed: the table
  gives `audit` and `bookkeeping` the same Normal and Low model, so that
  distinction stopped being observable (the two kinds resolve to the exact
  same value in every mode) -- kept as a `badkind` mutant instead, which
  tests the thing that is still observable (cloud.sh asking `models.sh` for
  the right kind name at all). Two new sections added at the end: the
  helper's answer against an independent `tomllib` read of `models.toml`,
  for every `[kinds.*]` row in both Normal and Low; and a repo-wide grep for
  any of the three model ids outside `models.toml`, `selftest.d/`,
  `pathfind_selftest.py`'s own fixture, `#`-comment lines, and backtick-quoted
  documentation references (drive.py's module docstring names Haiku's id in
  prose, for a human reading it) -- verified it actually goes red by
  temporarily reintroducing a literal and reverting.
- `89-usage-mode.sh`: removed the dead `PATHFIND_MODEL_CALLS_MAX=20` check
  (replaced with asserting it is NOT written); replaced the
  `limits.env`-override test for `USAGE_LOW_PROJ` with a scratch
  `models.toml` copy (`low_proj` edited to 60) pointed to via
  `$HAKUX_MODELS_TOML` for one tick -- "no limits.env override remains for
  these, that was the point" (models.toml's own comment), so the test has to
  move the dial the one way it still can.
- `87-ops-tick.sh`: Addendum 1's clock-step clamp (done earlier this lane,
  `_lane_idle_min()` floored at 0) plus its fixture leg, both still green
  (54/54) after the `bookkeeping` kind wiring.
- `88-window-budget.sh`: read in full; nothing in it names a model id tied to
  this migration (the one `claude-opus-5` string is an unrelated run-index
  fixture row for `board.sh`'s spend reserve). Its one real dependency on
  this lane's territory, `run-claude-job.sh`, is now fixed (see above) --
  5 checks that were failing against the broken sourcing (`a healthy job run
  exits 0` and friends) now pass.

## Verified (fragments run individually and together)

| fragment | result |
|---|---|
| 87-ops-tick.sh | 54/54 |
| 88-window-budget.sh | 50/50 |
| 89-usage-mode.sh | 49/49 |
| 99-lane-model-file.sh | 36/36 |
| 87+88+89+99 together | 189/189 |
| 78-sweep-remote.sh, 99-handback.sh, 99-limits-env.sh, 98-lane-shape.sh, 98-audit-outlet.sh, 99-handback-waiter.sh (the four non-territory `models.env` readers' own coverage) | 269/269 |

A full, no-`SELFTEST_ONLY` run was tried under a 590s timeout to see how far
it would get; it only reached the `arms.sh` fragments (alphabetically well
before 87-/88-/89-/99-) before the timeout killed it, so it adds no signal
about this lane's own changes. The brief's own words are the right call
here: "The selftest runs at fold (~60 min). Run the fragments you touch
before State: ready" -- that is the table above, not a full-suite run from
inside this session. The full ~60 minute run is lane.local's job at fold.

## For lane.local after the fold

See PR.md, "For lane.local after the fold".
