# routebuild1021: the dispatcher drives a title with no known path, and keeps the path it finds (#433)

State: ready

Lane: routebuild1021            Issue: #433 (0.5)
Base: master @ 656bcd1fe9
Files: docs/lanes/routebuild1021/PR.md, docs/testing/dispatcher.sh,
docs/testing/jobs/selftest.d/97-dispatch-snapshot-drive.sh, docs/testing/jobs/selftest.d/99-auto-route.sh,
docs/testing/titles/drive-profiles/generic.toml, docs/testing/titles/drive.py, docs/testing/titles/pathbook.py,
docs/testing/titles/pathclass_selftest.py, docs/testing/titles/pathknow/learned.py,
docs/testing/titles/routes/auto.route, docs/testing/titles/titlestate.py
Prediction: none: harness-only; no fps or pixel claim. The one behavioural claim (a title with no route is
  admitted and driven, and its book replayed on the next run) is checked by the selftests and mutants below,
  and on the device by the first dispatched run (proposed below, not started)
Needs device: yes, for the first proof run only (not started: all lanes are stopped until the owner lifts)
Needs NDK: no

Owner, 2026-10-21: "we would discuss 10 titles then hand them to the dispatcher and it would handle the rest",
"spend the remaining usage available to us to fill in the gaps so the measuring of titles isn't hapless button
mashing", and "This doesn't resolve the gap where the dispatcher would reject these requests if it doesn't have a
known path." Built in the interactive session (the Conker request was dropped; the Conker ISO is untouched).

## What was built

**The gap: the dispatcher refused a title with no path.** `titlestate.py suggest_route` named nothing for a
title with no proven route and no targets.toml route, and `admit()` refused an `any` route with no golden. So a
title that had never been run could only be queued by hand with `--find-route`.

- **`routes/auto.route`** (new) is the shared route for every title that has none of its own: one step,
  `drive generic 7200 mark`. The soak's TERM ends it long before 7200 s.
- **`titlestate.py`**:
  - `suggest_route` falls back to `auto` when `auto.route` exists in the routes tree, after the proven and
    configured checks (source `auto`).
  - `admit()` admits the auto route with no golden under the new clause `auto-route`, as it admits
    `--find-route`.
  - R3 is kept: the auto route is refused for a title that already has a proven route, and the refusal names
    that route.
  - The dispatcher needed no new code to attach it: the existing `ensure_route_attached` calls `suggest-route`
    for a request with no route (or `survey`), and never for find_route, remake_profile or path_broken.
- **The `proven_route` regex is unchanged, on purpose.** Teaching it to see drive.py's own `mark` (33+ routes
  use `drive generic 300 mark`) would widen R3 to titles it does not cover today. A run of the auto route that
  reaches play still counts through its verdict, as any route does.

**The book: what a run learns is kept for the next run of that title.**

- **`pathbook.py`** (new) uses pathfind's path schema and signature (16×12, SIG_MATCH 9).
  - `load(title_id)` returns the better of the drive-built path in `HAKUX_PATHS_DIR` and pathfind's path in
    `pathknow/paths`.
  - `build()` turns a run's trail into a path: it drops dead presses, and it cuts a loop only when the loop
    holds no menu step, because a menu cursor's position cannot be seen.
  - `save()` writes a path only when it beats the stored one (BETTER, in the docstring): finished beats
    unfinished, then the furthest point reached, then the faster time into play.
  - An unfinished pathfind path ranks at `FURTHEST_PATHFIND = 98`. A real comparison (below) showed it losing to
    a 6-step unfinished drive run; 43 of the repo's 207 paths are unfinished.
- **`drive.py`**:
  - With `TITLE_ID` set, the learned table and the book are the title's, not the shared `generic` profile's.
  - `replay_book()` runs before the policy. It presses the book's step for the current screen, found by signature
    near the book's cursor. A step that does not move its screen in `REPLAY_TRIES` (3) presses is left to the
    policy.
  - Every press goes to a trail with its screen and what the next capture showed. `finish()` writes
    `route-trail.json` and saves the book through `pathbook`.
- **The classifier's lean.** Below the confidence floor `classify.py` answers `unknown`, which sent every such
  screen to the blind ladder (72 of 88 captures on the Blinx 2 run 1-1792424727-lane.fpsnext1019-447829).
  - `lean()` sums pathclass's top 3 by family (menu, skip, wait, play). A family holding `LEAN_MASS` (0.45) picks
    the press before any ladder rung.
  - START is pressed only while the top 3 give gameplay less than 0.1, because START in play pauses the game.
- **D-pad fixed.** `UP`/`DOWN`/`LEFT`/`RIGHT` are now sent as hat flicks (`HAT`). hakuX's d-pad buttons do
  nothing, so every DOWN drive.py ever sent was a no-op: all 16 DOWN records in the learned table are `none`.
- **`learned.py`**:
  - `suggest(min_rank=)`, so a button recorded only as `none` no longer outranks the lean.
  - The table lives in `HAKUX_LEARNED_DIR`.
- **`generic.toml`**: `play_cycle`, `play_tap` and `stall_cycle` keep the player moving once in play.
- **`EXPLORE_LADDER`**: B moved to last, because on a menu B cancels back to the screen before.
- **`dispatcher.sh`**:
  - The soak runs with `TITLE_ID`, `TITLE_NAME`, `HAKUX_PATHS_DIR=$D/paths` and `HAKUX_LEARNED_DIR=$D/learned`.
  - `titles/pathbook.py` was added to `SCRIPT_DEPS` and to the snapshot list.
  - `titles/pathknow/paths/*.json` was added to `SNAPSHOT_GLOBS`, so a soak replays pathfind's 164 finished
    paths from the snapshot, not from the live checkout.

## Selftests

**`99-auto-route.sh`** (new) runs 8 cases on the real `titlestate.py` and two mutants:

| Case | Real code | Mutant that must fail it |
|---|---|---|
| No `auto.route`: suggest names nothing | ok | — |
| No `auto.route`: an `any` route with no golden is refused | ok | — |
| With `auto.route`: suggest gives `(auto, auto)` | ok | — |
| The auto route is admitted, clause `auto-route` | ok | admit branch removed: refused again (the old gap) |
| A non-auto `any` route is still refused | ok | — |
| A proven title: suggest gives its proven route | ok | — |
| A proven title: the auto route is refused (R3) | ok | R3 check dropped: admitted |

`auto.route` also passes `route.sh --check`.

**`97-dispatch-snapshot-drive.sh`** gained two legs:

- **Book leg.** `pathbook.py` is in the snapshot, and a book for 41430003 loads from `$BIN/titles/pathknow/paths`
  with `HAKUX_PATHS_DIR` empty. The mutant with the `SNAPSHOT_GLOBS` entry dropped loads nothing.
- **Auto-route leg.** From the snapshot, `suggest-route` gives `auto`, and `admit --route auto` admits under
  clause `auto-route`.

**`pathclass_selftest.py`** (standalone; no fragment runs it): 0 failures. New checks and the mutants they catch:

| Check | Mutant it catches |
|---|---|
| The lean presses pathclass's DOWN as `HATY:max` | d-pad sent as buttons |
| The lean beats a learned button recorded only as `none` | `min_rank` ignored |
| A book step is given up after `REPLAY_TRIES` presses on an unmoved screen | `REPLAY_TRIES` 99 |
| `pathbook` keeps same-screen DOWN, DOWN, A and drops a dead press | — |
| A loop with no menu step is cut; a loop through a menu is kept | the old naive loop cut (scratch mutant) |
| A finished pathfind path beats an unfinished drive one | — |
| An unfinished pathfind path is kept over an unfinished drive run, and replaced by a finished one | — |
| End to end: the next run of a title replays its saved path from the first step | — |

**`FURTHEST_PATHFIND`, hand check on the real Blinx 2 data.** Real code: drive `(False, 6, …)` >
pathfind `(False, 98, …)` = False. With the constant set to -1 (the old ranking): True, so the drive run would
have replaced the repo path.

**Full suite.** See the last section. `dispatcher.sh` is read by about 30 fragments, so this PR names no
`Selftest:` subset and the fold runs the full suite.

## Evidence on real frames, and its limits

Blinx 2 (4D530065) ran through `drive.py --sim route-frames --sim-step 6 --seconds 100 --mark`, with the real
pathclass on the RTX 2070:

- rc 0, 5 inputs.
- It replayed steps 4, 5 and 7 of the 9-step repo path on matching signatures, including on screens the
  classifier called `unknown`.
- It wrote the trail and a 5-step path to the sim's paths dir.

The sim's frames do not react to input. This checks the pipeline and its decisions, not that the presses reach
play. That is the device run's job.

## Known limits

- **Junk presses on animated menus.** A book recorded on an animated menu can keep presses that did nothing.
  Signature motion reads them as having done something. A later run that reaches play faster replaces the book
  (BETTER), so the junk costs time, not the path.
- **No device proof yet.** All lanes are stopped. The first run proposed is one Nova soak of NFS Hot Pursuit 2
  (45410028), queued with no route so the auto route attaches. It is not started until the owner says go.

## Full selftest run

Running at the time of this commit. The result will be recorded here before this PR is pushed.
