# snaptargets1018 (#433): the dispatcher snapshot ships titlestate.py but not targets.toml

## Session 1 (Sonnet 5), 2026-10-18

### Already-tried

| what | result |
|---|---|
| (none -- first session on this defect) | lane.local found and filed it 2026-10-18 01:39 PDT; no prior lane attempt exists |

### Reproduction (scratch DISPATCH_DIR, no device)

```
export DISPATCH_DIR=/tmp/snaptest-repro-1018 DISPATCH_SRC=.../docs/testing \
       SERIAL=ee317437 DISPATCH_TREE=... DISPATCH_REPO=...
bash -c '. dispatcher.sh selftest-not-a-subcommand >/dev/null 2>&1; snapshot_scripts'
export MAKE_XBOX_HDD=.../tools/make_xbox_hdd.py   # dispatcher.sh sets this; titlestate.py's
                                                   # saves.py import needs it directly too
TITLESTATE_DIR=/tmp/snaptest-repro-1018/titlestate DISPATCH_DIR=/tmp/snaptest-repro-1018 \
    python3 /tmp/snaptest-repro-1018/bin/titles/titlestate.py admit --title-id 4D5300D1 \
    --route-text-file /dev/null --find-route "fable lost chapters route find"
```

`ls bin/titles/` after `snapshot_scripts` holds classify.py, drive-profiles,
drive.py, pathclass.py, pathknow, route.sh, saves.py, titlestate.py,
waitfor_match.py -- no targets.toml. `admit` raises exactly the brief's
traceback: `admit -> known_path -> proven_route -> title_routes -> targets()
-> FileNotFoundError: .../bin/titles/targets.toml`.

### What else titlestate.py reads relative to HERE (not just targets.toml)

`admit`, run from the worker's snapshot (`profile_gate_check`, the only
titlestate.py subcommand the dispatcher invokes), is the one entry point
that matters. Traced every `os.path.join(HERE, ...)` / `os.environ.get(...,
os.path.join(HERE, ...))` in titlestate.py and which of admit's own call
paths reach each one:

| site | path | reached from admit()? | in snapshot today? |
|---|---|---|---|
| `targets()` (titlestate.py:219) | `HERE/targets.toml` | yes -- every call (via `title_routes`, `golden`/`disk_tid` indirectly) | **no** (the crash) |
| `routes_root()` (titlestate.py:580), used by `proven_route()` | `HERE/routes/<name>.route` | yes -- the `--find-route` branch's `known_path(broad=False)` -> `proven_route()`, for any title with a candidate route name (its own `targets.toml` `route` field, or a past dispatched result) | **no** |
| `TRANSITION_PATH` (titlestate.py:1119), used by `live_transition()` | `HERE/profile-transition.toml` | yes -- the `returning` and `first-run` state branches (the common, non-find-route claim path) | **no** |
| `pathknow_success()` (titlestate.py:1188) | `HERE/pathknow/paths/<TID>.json` | **no** -- only called with `broad=True`, and the only caller that ever sets `broad=True` is pathfind.py's own session code, which is not a dispatcher subcommand and is not shipped at all. `admit()`'s own call is hardcoded `broad=False`. | n/a -- not reached, so not needed |

`routes_root()`'s `HERE/routes` and `TRANSITION_PATH`'s
`HERE/profile-transition.toml` do not crash today the way `targets.toml`
does -- both opens are inside `try/except OSError`/`FileNotFoundError` in
`proven_route()` and `load_transitions()`. But both fail *silently* to the
behaviour the module's own docstring describes: with `routes/` missing,
`proven_route()` can never find a route's "mark gameplay" text, so
`known_path()` always reports "not known" even for a title with an already
-proven route -- R3's whole point (stop redoing find-route work) is
defeated, not merely degraded. With `profile-transition.toml` missing,
`live_transition()` always returns `[]`, so the transition grandfather
(the module docstring's own example: gta-sa's first-run keeps running past
R1 until a specific golden lands) never fires from the worker, and a run
that should be admitted on the transition clause is refused instead. Per
the brief ("Report the list; ship any that is missing"), I shipped both
alongside targets.toml -- all three are read by `admit()`, the one
subcommand the dispatcher actually runs from the snapshot.

Checked the other five scripts the brief named for the same class of bug:

- **route.sh**: every `$HERE`-relative read (`perf/pad.sh`,
  `drive-profiles/*.toml`, `waitfor_match.py`, `drive.py`) is already in
  `SCRIPT_DEPS`/`SNAPSHOT_GLOBS`. Nothing missing.
- **saves.py**: `HERE/../../../tools/make_xbox_hdd.py` reaches outside
  `docs/testing` entirely (repo-root `tools/`). Already handled: the
  `MAKE_XBOX_HDD` env override, which dispatcher.sh sets to the tree's copy
  (dispatcher.sh:736, with its own comment: "not under docs/testing and so
  not in the snapshot"). Nothing to do.
- **drive.py**: `HERE/../jobs` (models.py) and `HERE/../perf/pad.sh` are
  both already in `SCRIPT_DEPS`. Nothing missing.
- **classify.py**: its one relative path is derived from the *profile's own
  path* (passed in), not `HERE` -- resolves against `drive-profiles/`,
  already globbed. Nothing missing.
- **pathclass.py**: `HEAD` defaults to `HERE/pathknow/classifier/head.npz`,
  already in `SNAPSHOT_GLOBS`. The only other `HERE`-relative read
  (`pathknow/classifier/` for `prompts.py`, in `_zero_shot`) only runs when
  no trained head is loaded; since `head.npz` is shipped, that branch is
  never taken in the dispatched path. Pre-existing, out of scope, not
  touched (brief: don't widen beyond what a shipped script reads).

### What changed

1. `SNAPSHOT_GLOBS` gets two more entries: `titles/targets.toml` and
   `titles/profile-transition.toml` (single fixed files, each one glob
   pattern that matches exactly one path -- the same shape
   `titles/pathknow/classifier/head.npz` already has), and
   `titles/routes/*.route` (globbed like `drive-profiles/*.toml`, since a
   route file appears or changes per title the same way a profile does).
   `src_hash` already hashes everything `snapshot_globbed` returns by name
   and content, so adding or editing any of these three is a re-exec, same
   as a new drive profile.
2. `SCRIPT_DEPS` and the `snapshot_scripts` `for f in` list are untouched --
   data belongs in `SNAPSHOT_GLOBS`, per the brief, and the two lists stay
   equal (97-dispatch-snapshot-drive.sh and selftest.sh's own comparison
   both read `SCRIPT_DEPS`, not `SNAPSHOT_GLOBS`).
3. Did not touch `titlestate.py`: the gate's logic is correct, only the
   snapshot was incomplete.
4. Selftest: extended `97-dispatch-snapshot-drive.sh` with a new leg
   (`targets`) that builds a real snapshot and runs `titlestate.py admit`
   for a title with no golden and no known path (synthesized `--title-id`,
   not in `targets.toml`, with `--find-route`), asserting a JSON
   admit/refuse object comes back, not a traceback -- and that `routes/`
   and `profile-transition.toml` are present in the snapshot. The mutant
   (drop `titles/targets.toml` from `SNAPSHOT_GLOBS`) reproduces the
   original crash; removing it from the fix reinstates the failure
   (checked, see below).

### Verification

- `bash docs/testing/jobs/selftest.sh` run after the fix: green (full
  output in the PR).
- Reverted `SNAPSHOT_GLOBS` by hand (dropped `titles/targets.toml`) and
  reran just the new `targets` leg: it fails with the same
  `FileNotFoundError: .../targets.toml` the brief describes, confirming the
  leg is red on the un-fixed list (the required mutant check). Restored the
  fix afterward.

### Stop rule

Not triggered -- no selftest fragment failed twice for the same cause.
