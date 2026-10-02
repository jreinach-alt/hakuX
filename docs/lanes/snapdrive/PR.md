# snapdrive: the dispatcher's script snapshot carries the screen-aware driver (#433)

State: ready

Lane: snapdrive            Issue: #433
Base: master @ b71f92a12a
Files: docs/testing/dispatcher.sh, docs/testing/request.sh, docs/testing/jobs/selftest.d/97-dispatch-deploy.sh, docs/testing/jobs/selftest.d/97-dispatch-snapshot-rename.sh, docs/testing/jobs/selftest.d/97-dispatch-snapshot-drive.sh, docs/lanes/snapdrive/NOTES.md, docs/lanes/snapdrive/OUTBOX.md, docs/lanes/snapdrive/PR.md
Prediction: none: no arm. This is a harness deploy change (which scripts the dispatcher snapshots, and a queue-time route check). It does not affect emulator pixels or speed.
Needs device: no    Needs NDK: no

Release note (none): test harness only. No emulator code changes.

## What changed

Before this change, no dispatched run could play a `drive` route. The
worker's `$DISPATCH_DIR/bin/` held route.sh but not drive.py, classify.py,
waitfor_match.py or any profile, so `route.sh --check` failed with "no
profile" (routedriver2 NOTES section 4). I reproduced this in a scratch
DISPATCH_DIR with master's dispatcher.sh.

| scratch snapshot | files in bin/ | `bin/titles/route.sh --check sonic-heroes.drive.route` |
|---|---|---|
| master dispatcher.sh | 18 | exit 2, `drive 'sonic-heroes': no profile` |
| this branch | 67 (21 scripts + 5 tomls + 41 crops) | `route ok` |

- **dispatcher.sh**
  - The three .py files are added to `SCRIPT_DEPS` and to the
    `snapshot_scripts` list.
  - `titles/drive-profiles/*.toml` and `*/*.png` ship by glob
    (`SNAPSHOT_GLOBS`, `snapshot_globbed`), without `selftest/` fixtures.
  - `src_hash` covers those files by name and content. A new profile is
    therefore a re-exec and needs no edit to dispatcher.sh.
  - **A worker now runs `snapshot_scripts` at startup**, after hashing.
    Without this, the brief's "reaches the workers at their next re-exec"
    would not have held. The re-exec is performed by the previous version's
    code, which copies the previous list, so a newly listed file is missed
    until some later fold (vsh_score.py hit this on 09-25).
- **request.sh (brief item 4)**
  - `--route` now also checks the route as the run sees it: as
    `<rdir>/route.txt`, with the serving snapshot's route.sh. If that check
    fails, the serving tree's route.sh is tried, but only when that tree's
    dispatcher re-snapshots profiles.
  - It refuses a `drive` route whose profile will not be in the snapshot.
  - It also refuses every `waitfor`/`press-until` route. Their crops
    resolve to `<rdir>/refs/route.txt/`, which nothing writes, so such a run
    exits at line 1 and the soak runs on with no input. Master queues
    `castlevania-cod.first-run`; this branch refuses it and names the
    missing crop. Making crops travel is the next item (OUTBOX.md).
- **Selftests**
  - `97-dispatch-deploy`: the closure check resolves references against the
    referring file's directory and accepts paths. It was blind to every
    titles/ sibling before, and passed while drive was unshippable. A
    directory picked by variable must ship whole. There are mutants for each
    new form, plus the real tree with waitfor_match.py or a profile dropped.
  - `97-dispatch-snapshot-rename`: the mutant anchor is now
    indent-agnostic.
  - New `97-dispatch-snapshot-drive`: builds a snapshot, runs `--check` on
    every `.drive.route` from a result dir, resolves imports, checks that a
    new profile is hashed and shipped, and starts a held worker from an
    old-style bin/ (its mutant drops the startup snapshot). It also covers
    the four request.sh legs.

## Local checks (no CI while offline)

- `docs/testing/jobs/selftest.sh` (all fragments) on f68cb89cf9 (later
  commits touch only docs/lanes/snapdrive/): **2905 passed, 0 failed, all
  120 fragments**, exit 0.
- `docs/testing/preflight.sh --allow-tracker`: passed, and territory ok.
  Its coverage gate did NOT run (gh 403, account suspended). It fails open,
  so that leg is unchecked, not passed.
- `SELFTEST_ONLY="97-dispatch-deploy 97-dispatch-snapshot-rename 97-dispatch-snapshot-drive 89-title-verdict"`:
  all pass. Each mutant is red.
- Master request.sh vs this branch on `--route castlevania-cod.first-run`:
  master queued it; this branch refuses it.

## Deploy

No restart is needed. After the fold, a worker's next re-exec (the old code)
copies the new dispatcher.sh. The new worker then snapshots its own lists
at startup, which ships the driver and profiles.
