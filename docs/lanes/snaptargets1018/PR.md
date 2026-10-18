# snaptargets1018: the dispatcher snapshot ships titlestate.py but not targets.toml (#433)

State: ready

Lane: snaptargets1018            Issue: #433
Base: master @ 4a504d9aaa
Files: docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/97-dispatch-snapshot-drive.sh, docs/lanes/snaptargets1018/NOTES.md, docs/lanes/snaptargets1018/PR.md
Prediction: none: analysis-only (a dispatcher snapshot/selftest fix, no emulator code, no pixels or speed)
Needs device: no    Needs NDK: no

Release note (none): test harness only. No emulator code changes.

## What was wrong

A dispatched claim whose `admit()` reached `titlestate.py`'s `targets()`
crashed with `FileNotFoundError: .../bin/titles/targets.toml`, because the
dispatcher's script snapshot ships `titles/titlestate.py` but not the
`targets.toml` it opens beside itself. This hits every first-run or
find-route title (no golden short-circuits the admit path before
`targets()` for a title that already has one). Reproduced from a scratch
`DISPATCH_DIR` with master's `dispatcher.sh`, Fable: The Lost Chapters'
real request shape (`--find-route`, no `targets.toml` entry): the same
traceback the brief names.

Traced every other `HERE`-relative file `titlestate.py`'s `admit()` can
reach (the only titlestate.py subcommand the dispatcher's worker runs) and
found two more silently-missing files in the same snapshot: `routes/`
(read by `proven_route()` for the `--find-route` R3 check) and
`profile-transition.toml` (read by `live_transition()` for the ordinary
returning/first-run claim path). Neither crashes -- both opens are
try/excepted -- but both silently defeat the behaviour the gate's own
docstring describes (R3's "don't redo a proven route blind", and the
transition grandfather). Full trace and the other five scripts' review are
in NOTES.md.

## What changed

- `SNAPSHOT_GLOBS` (docs/testing/dispatcher.sh) gains `titles/targets.toml`,
  `titles/profile-transition.toml` (single-file globs, same shape as the
  existing `titles/pathknow/classifier/head.npz`) and `titles/routes/*.route`
  (globbed like `drive-profiles/*.toml`). `src_hash` already covers
  everything `snapshot_globbed` returns by name and content, so editing any
  of these three is a re-exec, the same as a new drive profile.
- `SCRIPT_DEPS` and the `for f in` list in `snapshot_scripts` are untouched
  -- this is data a shipped script picks up at run time, which is
  `SNAPSHOT_GLOBS`'s documented home, not `SCRIPT_DEPS`'s.
- `titlestate.py` itself is unchanged: the gate's logic is correct, the
  snapshot was incomplete.
- Selftest: a new `targets` leg in `97-dispatch-snapshot-drive.sh` builds a
  real snapshot and runs `titlestate.py admit --find-route` for a title
  with no `targets.toml` entry and no known path, asserting JSON comes back
  (not a traceback), and that `routes/` and `profile-transition.toml` landed
  in the snapshot. A mutant that drops `titles/targets.toml` from
  `SNAPSHOT_GLOBS` reproduces the crash. Checked both ways by hand: reverted
  the `SNAPSHOT_GLOBS` fix and reran the leg -- 5 of its checks go red, the
  same shape as the brief's traceback; reapplied the fix and reconfirmed
  green. Also fixed `mutant_drop`'s line-continuation handling, which my own
  edit exposed (a word placed right after a backslash-newline never matched
  the old byte-level matcher).
- Found and fixed, scoped to just this leg: `sd_env_at`'s mutant files have
  no `devices.sh` beside them, so sourcing a mutant dispatcher.sh died
  before `snapshot_scripts` was even defined -- the two pre-existing
  mutants in this file (`no-pathclass.sh`, `no-head.sh`) have never
  actually exercised `snapshot_scripts`; they pass by checking file
  *absence*, which holds whether or not anything ran. Fixed only for the
  new `targets` leg (`cp devices.sh` beside its own mutant before sourcing);
  left the shared helper and the two pre-existing legs untouched -- fixing
  `sd_env_at` centrally would also expose that `SCRIPT_DEPS`'s mutant never
  actually drops anything from the real copy loop (a second, independent,
  pre-existing bug), which is outside this brief's files. Detail in
  NOTES.md.
- Full `docs/testing/jobs/selftest.sh` (148 fragments), run twice: 3606
  passed, 1 failed both times, the same pre-existing failure both times
  (`66-status-titles.sh`, a README.md/home_page.py page-agreement check,
  unrelated to this defect). Reproduces identically with only the prior two
  lane commits checked out (no dispatcher.sh/selftest edits applied) --
  confirmed pre-existing on master, not a regression from this change. Not
  fixed: outside this brief's files list.

Selftest: 97-dispatch-snapshot-drive.sh (new `targets` leg)
