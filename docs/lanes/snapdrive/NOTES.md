# snapdrive (#433): the dispatcher's script snapshot carries the screen-aware driver

## Session 1 (Opus 5.5), 2026-10-02

### What was wrong (reproduced in a scratch DISPATCH_DIR)

The master `dispatcher.sh`, sourced against this tree with a scratch
DISPATCH_DIR, ships 18 files to `bin/`. `bin/titles/` holds route.sh,
saves.py and titlestate.py and nothing else, and
`bin/titles/route.sh --check routes/sonic-heroes.drive.route` exits 2 with
`drive 'sonic-heroes': no profile .../bin/titles/drive-profiles/sonic-heroes.toml`.
That is the live failure from routedriver2 NOTES section 4. With this
branch's `dispatcher.sh` it ships 67 files: 21 scripts plus 46 profile files
(5 tomls and their 41 crops, none of `selftest/`), and the check passes.

### What changed

1. **dispatcher.sh lists.** `titles/drive.py`, `titles/classify.py` and
   `titles/waitfor_match.py` are added to both `SCRIPT_DEPS` and the
   `snapshot_scripts` loop. The copy body moved into `snapshot_one` unchanged
   (write beside, then rename).
2. **Profiles by glob.** `SNAPSHOT_GLOBS="titles/drive-profiles/*.toml
   titles/drive-profiles/*/*.png"`, and `snapshot_globbed` lists their matches
   minus `*/selftest/*`. `snapshot_scripts` copies them. `src_hash` hashes
   each one's name and content, so adding, renaming or editing a profile or
   crop triggers a re-exec, and dispatcher.sh never needs editing for a new
   title.
3. **A worker snapshots at startup** (after hashing). I found this while
   checking the brief's premise that the change "reaches the live workers at
   their next re-exec". As written, it would not have. The re-exec is carried
   out by the previous version's `snapshot_scripts`, which uses the previous
   list. It copies the new dispatcher.sh, but none of the files this fold
   adds, and nothing re-snapshots until a later fold moves the hash. This is
   the same gap that left `vsh_score.py` out of `bin/` on 2026-09-25. With
   the startup snapshot, the first re-exec after this fold ships everything.
   Hash first, then snapshot: if the tree changes between the two, the
   snapshot is newer than the hash, and the next tick re-execs.
4. **request.sh (brief item 4).** `--route` now also checks the route the way
   the run will see it. The text goes into a temp `route.txt`, and the
   serving snapshot's `route.sh` checks it. If that fails, the serving tree's
   `route.sh` is tried, but only when that tree's dispatcher.sh has
   `snapshot_globbed()`, because a worker re-snapshots from that tree before
   it claims anything. With neither present, this tree's route.sh checks the
   copy. This catches two failures:
   - **A `drive` profile the serving snapshot lacks.**
   - **Every `waitfor`/`press-until` route.** The dispatcher writes the route
     text to `<rdir>/route.txt`, so `ref_path` resolves a crop to
     `<rdir>/refs/route.txt/<name>.png`, and nothing writes that file. In a
     dispatched run, `validate()` exits 2 at once and the soak runs on with
     no input. That is the failure lane.routedriver saw. Master's request.sh
     queues `castlevania-cod.first-run` (checked: `queued 1790943788-sd-...`).
     This branch refuses it and names the missing crop.
     `castlevania-cod.first-run` is the only route with such steps today.

### Selftests

- `97-dispatch-deploy`: the closure check now resolves a reference against
  the directory of the file that makes it, and reads paths (`titles/x.sh`,
  `../perf/pad.sh`). Before, it read every reference against `docs/testing/`
  and only as a bare name. So route.sh's `$HERE/drive.py` and classify's
  `from waitfor_match import` looked for `docs/testing/drive.py`, found
  nothing, and **passed**. A directory a script picks a file from by a
  variable (`"$HERE/drive-profiles/${w[1]}.toml"`) must now ship whole, minus
  `selftest/`. New mutants:
  - a subdirectory sibling, in `$HERE/` form and in import form;
  - an unshipped file in drive-profiles/, plus a fixture that must NOT be
    asked for;
  - the real tree with `titles/waitfor_match.py`, then
    `drive-profiles/sonic-heroes.toml`, dropped from the shipped set. Each is
    named, along with the file that needs it.
- `97-dispatch-snapshot-rename`: the mutant's anchor no longer assumes
  8-space indentation, because the cp line moved into `snapshot_one`.
- **New `97-dispatch-snapshot-drive`** builds a real snapshot in a scratch
  DISPATCH_DIR and checks:
  - **Route check:** every `routes/*.drive.route` passes `route.sh --check`
    from a result dir (`route.txt`), using the snapshot's route.sh.
  - **Its mutant:** with `drive-profiles/` removed, the check fails with "no
    profile".
  - **Imports:** `drive`, `classify` and `waitfor_match` resolve inside
    `bin/titles/` (find_spec, which needs no PIL). Where PIL and numpy exist,
    a full import plus `load_profile` runs from the snapshot.
  - **New profile:** one added to a scratch source moves `src_hash`, appears
    in the next snapshot (toml and crop), and an edit to its crop moves the
    hash again.
  - **Worker startup:** a real `dispatcher.sh worker`, held so it claims
    nothing, with a bin/ holding only the new dispatcher.sh and devices.sh,
    has drive.py and the profiles once started. Mutant: with the startup
    `snapshot_scripts` removed, they are absent.
  - **request.sh legs:** a drive route is queued against a snapshot that has
    its profile. The waitfor route is refused ("no reference crop"). A drive
    route is refused against a snapshot without profiles and no serving tree
    ("no profile"), and queued when the serving tree ships profiles.

### For the next lane (do not repeat)

- **Do not treat `route.sh --check routes/<x>.route` in your tree as proof a
  dispatched run can play `<x>`.** The run plays `<rdir>/route.txt` with
  `$DISPATCH_DIR/bin/titles/route.sh`. Check that copy (request.sh now does).
- **Waitfor crops do not travel.** Making them travel is the next item, in
  OUTBOX.md. It is not done here because it changes the request format and
  where the dispatcher writes the route.
- **The startup snapshot fixes the "new file misses the first re-exec" gap
  only after this fold is live.** This fold's own deploy is fine: the old
  worker copies the new dispatcher.sh, and the new worker snapshots at start.
- **A file removed from the tree stays in `bin/`.** This was already true for
  scripts and now also holds for profiles. It is harmless: a stale profile is
  only read by a route that names it, and request.sh checks against the
  serving tree too.
