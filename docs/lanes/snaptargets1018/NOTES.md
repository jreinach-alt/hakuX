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

### The mutant leg needed devices.sh beside it to run at all

`sd_env_at()` (this fragment's helper for the `no-pathclass.sh`/`no-head.sh`
mutants) sources a standalone mutant file whose own directory becomes
dispatcher.sh's `HERE`. dispatcher.sh's first two real lines are `.
"$HERE/devices.sh"` then `device_env ... || exit 2`; with no `devices.sh`
copied beside the mutant, sourcing dies there -- before `snapshot_scripts`
is even defined -- and the whole `( ... )` subshell exits 2. My first
`no-targets.sh` mutant run showed exactly that: `$SD/dnt/bin` never existed
at all, not just without `targets.toml`.

This also affects the two pre-existing mutants in this file, but silently:
both check file *absence*, which is trivially true whether or not
`snapshot_scripts` ever ran, so `no-pathclass.sh` and `no-head.sh` have
never actually exercised `snapshot_scripts` and still reported `ok`. I
confirmed this by fixing it once, centrally, in `sd_env_at()` itself (copy
`$TESTING/devices.sh` beside the mutant before sourcing) and re-running: the
`no-pathclass.sh` leg turned red -- *"still shipped it"* -- because
`snapshot_scripts`'s real copy loop is a separate hardcoded `for f in ...`
list, not the `SCRIPT_DEPS` variable `mutant_drop` edits, so dropping a word
from `SCRIPT_DEPS` text never stopped the copy. That is a second,
independent latent bug in the `SCRIPT_DEPS`-mutant pattern, pre-existing,
and out of this brief's scope (targets.toml/SNAPSHOT_GLOBS only) --
reported here, not fixed, per "do not widen the snapshot beyond what a
shipped script reads" and to avoid changing a leg I wasn't asked to touch.

Fix actually shipped: a `cp "$TESTING/devices.sh" "$SD/devices.sh"` scoped
to just the new `targets` leg, right before its own `sd_env_at` call --
not in the shared helper, so `no-pathclass.sh`/`no-head.sh` are untouched
and keep passing exactly as before (still for the wrong reason, but that is
not this brief's defect to fix). Next lane touching this file: `sd_env_at`
itself is the right place to fix the `SCRIPT_DEPS` pattern, and it will
flip `no-pathclass.sh` red when you do -- expected, not a regression.

### Verification

- `bash docs/testing/jobs/selftest.sh`, full run, twice: 3606 passed, 1
  failed, both times, same failure both times -- `66-status-titles.sh`'s
  `check --pages passes when every page agrees...` (`PAGE README.md: the
  Playable line is not the numberless form home_page.py rewrites`).
  Reproduces alone (`SELFTEST_ONLY=66-status-titles.sh`), and reproduces
  identically with only the two committed lane commits checked out (no
  `dispatcher.sh`/`97-dispatch-snapshot-drive.sh` edits applied) --
  pre-existing on master, unrelated to this defect (README.md/status.sh/
  home_page.py, no file this lane touches). Not fixed: out of the brief's
  files list.
- `SELFTEST_ONLY=97-dispatch-snapshot-drive.sh`: 27 passed, 0 failed, both
  before and after the full run above.
- Reverted `SNAPSHOT_GLOBS` by hand (`git checkout -- docs/testing/dispatcher.sh`,
  dropping the fix) and reran just the new `targets` leg: 5 of its checks go
  red (`targets.toml`/`profile-transition.toml`/`routes/` absent, `admit`
  returns a traceback not JSON, and the mutant's own anchor check), the same
  failure shape the brief describes. Reapplied the fix from a saved patch
  afterward and reconfirmed green.

### Stop rule

Not triggered -- no selftest fragment failed twice for the same *new*
cause. The one full-suite failure above repeats across runs, but it is the
same pre-existing cause each time, not a new one introduced by this change.
