# snaptargets1018: the dispatcher snapshot ships titlestate.py but not targets.toml (#433)

State: draft

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
  `SNAPSHOT_GLOBS` reproduces the crash (checked by hand, see NOTES.md); the
  leg is red against master and green with this fix.

Selftest: 97-dispatch-snapshot-drive.sh (new `targets` leg)
