# lane.locations1014 -- NOTES

## Resume state (attempt 2, 2026-10-14)

Attempt 1 left no trace to build on: `git log origin/master..HEAD` on this
branch is empty (the branch tip is still exactly `origin/master` @
`76bef8b162`), there is no `docs/lanes/locations1014/` directory, and both
session log files under `logs/lane/locations1014.*.json` are zero bytes.
Whatever attempt 1 did, it committed nothing and wrote nothing to disk
before its turn ended -- there is no partial work to continue and no stated
reason it stopped. Starting the brief from scratch in this attempt.

## Scope decisions made before writing code

- System of record is `pm/title-registry.tsv`'s sibling, `pm/title-locations.tsv`
  (TSV only, per the 10-14 revision at the top of the brief -- no SQLite).
- `pm/` lives under the host work dir (`/home/justin/hakux-work/pm`), not
  inside this git worktree -- same convention `title_registry.py` uses
  (`DEFAULT_ROOT`). The new `title_locations.py` follows the same `Paths`-style
  convention so it composes with `read_registry()`.
- `docs/testing/title_registry.py` is untouched (lane.titledb1014 holds it).
  New code goes in `docs/testing/title_locations.py` only.
- id_source trust order (xbe-cert > name-prefix > manifest > push-log) maps
  onto real sources found on disk:
  - `console`: `titles/console-inventory-*.csv` already carries a `title_id`
    column (built and verified elsewhere) -- read as `manifest`, not re-read
    from a live XBE (no console network contact from this lane; console
    access is FTP, out of scope and not permitted here anyway).
  - `d-xiso` (`/mnt/d/hakux-staging/xiso`): filenames are `<TID>-name`
    (`name-prefix`), but `xiso/manifest.csv` (the stager's manifest, with a
    real sha256) is cross-matched by `source_path`/filename first and wins
    as `manifest` when it matches; falls back to `name-prefix`.
  - `d-cache` (shuffle-cache, a symlink to `/mnt/d/hakux-staging/shuffle-cache`):
    always `<TID>-name`, `name-prefix`.
  - `d-other` (`/mnt/d/hakux-staging/{ingest,kfc,owner1004,sports,staging,
    staging-linux,sweep,thor-copy,nova-archive-1008}`, filtered to
    `*.iso`/`*.xiso.iso`): some files are `<TID>-name` (`name-prefix`); some
    are the owner's original names with NO id in the filename at all --
    confirmed on disk: `sports/MLB_SlugFest_2003.xiso.iso` and
    `MLB_SlugFest_2004.xiso.iso` (the brief's own falsifier pair, for real,
    not just a fixture), and `owner1004/Deathrow (USA).xiso.iso`,
    `owner1004/MechAssault.iso`. These get a direct `xbe-cert` read (cheap:
    local uncompressed file, a handful of seeks, no decompression).
  - `d-archive` (`/mnt/d/Xbox`, 215 `.7z` files, zero name-prefixed -- every
    filename is the owner's redump name): `xbe-cert` only, read by streaming
    the archive's single `.iso` member through `7z.exe x -so` (Windows path,
    via `wslpath -w`; WSL path args to 7z.exe gave "Access is denied") into a
    forward-only reader that never writes the decompressed image to the
    Linux disk and never seeks backward. This is the slow path: the root
    directory's sector offset isn't known in advance, so a worst case reads
    forward through most of a solid LZMA stream per archive. Correct and
    tested (see selftest), but a full 215-archive first build is a
    multi-minute-per-archive, several-hour job -- too long for one headless
    turn. This session ran it with `--archive-limit` capped for a live
    demonstration (see PR.md for the count and findings) and documents the
    uncapped run as the follow-up the owner/lane.local should queue as a
    background job, not something this session can block a turn on.
  - `nova`: a live `adb -s ee317437 shell ls -l` of the games folder
    (`name-prefix`; every filename observed is `<TID>-name`), not the stale
    `hardware/titlepush/listing-nova.txt` (10 days old) -- the brief asks for
    the Nova's *live* listing.
  - `thor`: offline (owner, ~10-27 earliest return). No live read is
    possible. Seeded from `hardware/titlepush/listing-thor.txt` (the last
    push log) with `id_source=push-log` and `stale=thor-offline` -- this is
    the one place `push-log` is the right trust label: the only evidence is
    an old push log, not a live stat.

## wt/pathfind/scratch/day1014.py -- NOT edited directly

The brief asks to wire `copy_exists_elsewhere` into
`wt/pathfind/scratch/day1014.py`'s `drop_failed`. That file lives in a
*different* git worktree (`wt/pathfind`, branch `pathfind`) of the same
repo -- confirmed with `git worktree list` (gitdir
`/home/justin/hakuX/.git/worktrees/pathfind` vs this lane's
`.../worktrees/locations1014`). The lane rules forbid running git in a tree
that is not mine; editing the file there without git would leave an
uncommitted, unreviewable change sitting in another lane's live worktree,
and the file's own header says a chain (`lane.local`, TAG 1014d) is actively
driving Nova pushes/deletes with it right now. Editing a script that is
plausibly mid-run, with no way to commit or roll back the edit from here, is
the kind of blast-radius risk the lane contract asks me to avoid rather than
shortcut past.

Also: `drop_failed`'s existing Nova-side matching (`on_nova()`) already
keys off `tid` (the title_id), not a name -- `[x for x in ls(...) if
x.startswith(tid + "-")]`. It is not the name-matching the brief is
guarding against; that risk is real in `dprep1007.py`/`day1014.py`'s D:\\Xbox
argument handling (`glob.glob(D + "/" + arg + "*")`, matched against the
operator's own typed prefix, not against a verified title_id) and in any
"is there another copy" check that compares archive *names* instead of
title_id -- today there is no such check in `drop_failed` at all (the
comment "archive stays on D:" is asserted, never verified).

Decision: ship `copy_exists_elsewhere(title_id, location, bytes)` in
`title_locations.py`, fully tested, and name the exact call site and diff
in PR.md as a follow-up for a pathfind-lane PR (or a board request) to land,
rather than editing it from here.

## dcandidates returns 0 on the live table -- the gate is working, not broken

A live `build` + `dcandidates` run found 0 D: cleanup candidates even though
every console title also has an on-disk copy somewhere under D:. Cause:
`console-inventory-*.csv`'s `size_bytes` is the console's game-folder size
(filesystem overhead included), which is consistently ~1-1.3 MB off from the
matching D: XISO's exact byte count, and no console row carries a sha256.
`copy_exists_elsewhere` requires an exact bytes match or a sha256 match
before it will name a copy as verified -- it correctly refuses to call
these two numbers equal, so it reports no backing copy rather than guess.
This is the gate behaving exactly as specified (never approve a delete on a
fuzzy match), not a defect. Follow-up named in PR.md: either compute a real
console-side sha256 (slow: would mean reading every title off the console
once) or get an owner-approved size-tolerance rule before dcandidates can
usefully report console-verified matches. Confirmed the host-tools report
snippet (`title_locations_report.py`) computes the same 0 by mirroring
`cmd_dcandidates`'s exact filter -- an earlier draft of that snippet used a
looser "matches any other location" check and wrongly got 94, counting
D:-to-D: matches that are not real candidates under the brief's own
console/d-archive restriction.
