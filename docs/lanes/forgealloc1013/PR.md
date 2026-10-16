# lanes stop opening forge PRs directly, and a forge number ahead of GitHub raises an alarm (#433, 0.5)

State: ready

Lane: forgealloc1013            Issue: #433
Base: master @ 3c2338eb2b
Files: docs/testing/jobs/roles/lane.md, docs/testing/jobs/handback.sh, docs/testing/jobs/gh-shim/gh, docs/testing/jobs/gh-shim/forge_prsync.py, docs/testing/jobs/gh-shim/smoke_live.py, docs/testing/jobs/gh-shim/create_refusal_test.py, docs/lanes/forgealloc1013/NOTES.md, docs/lanes/forgealloc1013/PR.md, docs/lanes/forgealloc1013/idlewatch.py.new, docs/lanes/forgealloc1013/idlewatch.py.diff, docs/lanes/forgealloc1013/forge_alloc_selftest.py, docs/testing/fleet.py, docs/testing/jobs/selftest.d/96-fleet-registry.sh, docs/testing/jobs/selftest.d/98-lane-shape.sh
Prediction: none: harness
Needs device: no    Needs NDK: no
Release note (none): harness

## Why

`gh pr create`/`gh issue create` POST straight to the local forge with no
allocator, and can take a PR/issue number GitHub hasn't allocated yet. That
leaves the forge ahead of GitHub and blocks every new issue and lane PR
until someone runs `issue_mirror.py backfill` by hand -- which happened
twice, 10-12 and 10-13, costing hours each time. The fix is an allocator
lanes always go through: write `docs/lanes/<lane>/PR.md` and push;
`forge_prsync.py` opens the forge PR itself via `issue_mirror.py new`,
which reserves the number on GitHub first.

## Status

Step 0 (sync repo `gh`/`forge_prsync.py` with the installed copies), Task 1
(`roles/lane.md`), Task 2 (`handback.sh`'s two resume prompts) and Task 3
(the shim's two refusals, every other caller of `pr create`/`issue create`
under `docs/testing` cataloged, `smoke_live.py` and a new
`create_refusal_test.py`) are done; selftests and live smoke pass. Full
writeup in `docs/lanes/forgealloc1013/NOTES.md`.

**WAITING** (not mine to fix, named in NOTES.md): `docs/testing/jobs/status.sh`
line ~674 calls `gh issue create` to recreate the "harness: live status"
issue if it's ever deleted; that call will now be refused by the shim.
Needs a small fix from whoever owns `status.sh` next (an `ISSUE-REQUEST:`
line, or a narrow exemption) -- `status.sh` is explicitly not my territory.

Task 4 (a zero-GitHub-read forge-ahead alarm in
`~/hakux-work/host-tools/idlewatch.py`, staged as `.new`+`.diff`, with its
own selftest) is now done too; see `NOTES.md` for the two detection
candidates considered and why the installed `.issue-mirror.json`/
`status/issue-mirror.txt` route was rejected (up to a 24 h blind spot).

Task 5 is done too: `fleet.py`'s "READY with no pipeline label" FAIL was a
false-positive generator against `foldqueue.sh`, which folds a `lane/*`
branch off its own PR.md directly and never touches a GitHub label. Added
`foldqueue_status()` (reads `foldqueue.log`) and a staleness bound
(`FOLDQUEUE_STALE_S`, three missed 15-min ticks) so the FAIL only fires
when foldqueue.log also has nothing recent to say. Updated both selftests
that exercised the old text (`96-fleet-registry.sh`,
`98-lane-shape.sh`) with new fixtures proving the suppression and the
non-regression case side by side; 123 passed, 0 failed. Full writeup in
`NOTES.md`.

All five tasks for this lane are now done.

## Install, once `State: ready`

Both from the master tree, after fold, run by lane.local -- not by this
lane, and not before `State: ready`:

```
bash docs/testing/jobs/gh-shim/install.sh
```

and, for the idlewatch alarm (write `.new`, then `mv`; never edit a
running script in place):

```
cp ~/hakux-work/host-tools/idlewatch.py ~/hakux-work/host-tools/idlewatch.py.bak
cp docs/lanes/forgealloc1013/idlewatch.py.new ~/hakux-work/host-tools/idlewatch.py.new
mv ~/hakux-work/host-tools/idlewatch.py.new ~/hakux-work/host-tools/idlewatch.py
```
