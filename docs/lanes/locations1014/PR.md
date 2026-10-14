# A tracked listing of which title is where, keyed by title_id

State: ready

Lane: locations1014            Issue: #433
Base: master @ 76bef8b162
Files: docs/testing/title_locations.py, docs/testing/selftest_title_locations.py, docs/lanes/locations1014/NOTES.md, docs/lanes/locations1014/PR.md, docs/lanes/locations1014/host-tools/title_locations_report.py, docs/lanes/locations1014/host-tools/INSTALL.md
Prediction: none: analysis-only, no device/pixel claim
Needs device: no (one live, read-only `adb shell ls` of the Nova)    Needs NDK: no

Release note (performance|stability|rendering|other|none): none

## What this is

`docs/testing/title_locations.py`: a generated `pm/title-locations.tsv`
(one row per copy of a title: title_id, location, path, bytes, sha256,
id_source, seen_utc, mtime, stale), keyed by title_id only -- never a name.
`build`/`check`/`show`/`copies`/`dcandidates`/`selftest` CLI, plus a library
surface (`read_table`, `copies()`, `copy_exists_elsewhere()`) for other
tools to call. Joined to `pm/title-registry.tsv` by title_id;
`docs/testing/title_registry.py` itself is untouched (lane.titledb1014
holds it).

id_source records how each row's id was actually read, in trust order:
`xbe-cert` (the default.xbe certificate, read directly -- for a `.7z` this
streams the archive's `.iso` member through `7z.exe x -so` into a
forward-only reader that never writes a decompressed disc image to the
Linux disk, and gives up past a byte cap rather than draining a whole
multi-GB image), `name-prefix` (this project's own `<TID>-name` filename
convention), `manifest` (a pre-verified catalog row this lane didn't itself
re-read: `xiso/manifest.csv`, `titles/console-inventory-*.csv`), `push-log`
(the Thor's last push listing, offline, nothing to re-read live). No name
matching anywhere; a file whose id can't be read is `UNRESOLVED`.

## Live build (this session, against real data)

1882 rows total:

| location  | rows | UNRESOLVED | notes |
|-----------|-----:|-----------:|-------|
| console   |  832 |          0 | from `console-inventory-*.csv`, `manifest` |
| d-archive |  214 |        176 | `--archive-limit 40` this run (see below); 174 "not read this build", 2 real failures |
| d-xiso    |   30 |          0 | `xiso/manifest.csv` cross-matched, else `name-prefix` |
| d-cache   |   49 |          0 | `name-prefix` |
| d-other   |   70 |          0 | mixed; includes both real falsifier pairs below, read by direct `xbe-cert` |
| nova      |  195 |         76 | live `adb shell ls`; the 76 are nxdk graphics-test fixtures (`pgraph-*.iso` etc.), correctly not real games |
| thor      |  492 |         21 | offline; seeded from the last push log, `id_source=push-log`, `stale=thor-offline` |

`check` correctly exits non-zero (UNRESOLVED rows remain, by design -- see
below). `python3 docs/testing/selftest_title_locations.py` passes all 29
checks, including all 4 of the brief's falsifier pairs as hermetic fixtures
and the mutant (a name-prefix gate matches the wrong title in a falsifier
pair; the real `copy_exists_elsewhere` refuses the same match).

### Falsifiers confirmed for real on disk, not just as fixtures

`d-other` has no id in the filename at all for two of the brief's named
pairs -- resolved correctly by direct `xbe-cert` reads, never by name:
`sports/MLB_SlugFest_2003.xiso.iso` vs `MLB_SlugFest_2004.xiso.iso`, and
(same risk, not a named pair but the same shape) `owner1004/Deathrow
(USA).xiso.iso` vs `MechAssault.iso`. `copies <tid>` for each SlugFest
title_id returns its own distinct, correct row set.

### d-archive: 40/215 sampled this session, not the full set

`/mnt/d/Xbox` is 215 `.7z` files, none name-prefixed (every filename is the
owner's own redump name) -- `xbe-cert` is the only possible id_source, read
by streaming the archive's `.iso` member forward-only through `7z.exe x
-so` (never unpacked to disk, never written to the Linux disk). Per-archive
cost is real: directory tables are usually early in the stream (as little
as 0.15s), but a worst case reads forward through most of a solid LZMA
stream -- several minutes. A full 215-archive build is a multi-hour job,
too long for one headless turn; this session ran `--archive-limit 40` for
a live demonstration. **Follow-up: the owner/lane.local should queue the
uncapped `title_locations.py build` as a background job**, not something a
lane session blocks a turn on.

Found and fixed one real bug this way: `XBE_CERT_READ_CAP` was 300 MiB,
below the second XDVDFS header base (`0x18300000`, ~387 MiB) that some
titles only resolve through -- confirmed on `AFL Premiership
(Australia).7z`, which has no root directory at base 0 at all. Raised to
480 MiB; re-verified the title now resolves (`54510101`, `AFL
Premiership`, 5.4s) and selftest stays green.

### dcandidates: 0 candidates, and that is the gate working correctly

`title_locations.py dcandidates` returns 0 on the live table, even though
every console title also exists somewhere under D:. Cause:
`console-inventory-*.csv`'s `size_bytes` is the console's game-folder size
(filesystem overhead included), consistently ~1-1.3 MB off from the
matching D: XISO's exact byte count, and no console row carries a sha256.
`copy_exists_elsewhere` requires an exact bytes-or-sha256 match before
naming a copy as verified, so it correctly refuses to call these equal
rather than guess -- this is the safety behavior the brief asked for, not
a defect. **Follow-up, needs an owner call**: either compute a real
console-side sha256 (slow -- means reading every title off the console
once) or get an owner-approved size-tolerance rule before `dcandidates`
can usefully report console-verified matches.

## Part 3: host-tools report (not wired into the live hourly_report.sh)

`docs/lanes/locations1014/host-tools/title_locations_report.py` is a
read-only reporter (table age, per-location row/UNRESOLVED counts, the
same `dcandidates` count) matching the brief's "do not write to
`/home/justin/hakux-work/host-tools`" instruction -- it's a lane-owned copy,
with `INSTALL.md` naming the exact one-line splice into the real
`hourly_report.sh` (and the copy step into the real `host-tools/`) for
whoever folds this lane to make. It fails soft (one line, exit 0) if
`title_locations.py` hasn't folded to `$R` yet or the table doesn't exist.

## Not done: wiring into wt/pathfind/scratch/day1014.py

The brief asks to wire `copy_exists_elsewhere` into
`wt/pathfind/scratch/day1014.py`'s `drop_failed`, and into
`dpush1007.sh`/novafree callers. `day1014.py` lives in a *different* git
worktree (`wt/pathfind`, branch `pathfind`) of the same repo, and its own
header comments say a chain is actively driving Nova pushes/deletes with
it right now. The lane contract forbids running git in a tree that isn't
mine, and editing a plausibly-live script with no way to commit, review,
or roll the edit back from here is exactly the blast-radius risk the
contract asks a lane to avoid rather than shortcut past. See
`NOTES.md` for the full reasoning, including that `drop_failed`'s existing
Nova-side check (`on_nova()`) already keys off `tid`, not a name -- the
real name-matching risk is in `dprep1007.py`'s D:\Xbox argument handling
(`glob.glob(D + "/" + arg + "*")`, matched against an operator-typed
prefix) and in the fact that `drop_failed` has no "another copy exists"
check at all today (the comment "archive stays on D:" is asserted, never
verified).

**Named follow-up for a pathfind-lane PR or board request**: in
`drop_failed`, before deleting an archive copy, call
`copy_exists_elsewhere(tid, "d-archive", bytes)` (import from
`docs/testing/title_locations.py`) and refuse the delete on `None`,
replacing any name-based "archive stays on D:" assumption with a verified
check. Same call, `location="nova"`, for the Nova-side delete path once one
exists. `dpush1007.sh`/novafree were read this session; no name-based
delete gate was found in them beyond what's named above -- if one exists
elsewhere in that chain, it wasn't reachable from this worktree to
confirm.

## Note on registry columns

The brief suggests adding `copies`/`where` columns to `title_registry.py`
once titledb1014 has folded. Not done here (that file is held). Named as a
follow-up once titledb1014's PR lands -- `title_locations.copies(tid)` is
already the right call to back such columns.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
