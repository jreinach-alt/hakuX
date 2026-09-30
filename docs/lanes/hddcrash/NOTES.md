# lane.hddcrash -- #622's titles disk crashes hakuX at start-up (#397)

PR #629. Base master @ a3681ccb0b.

## Verdict

**The image was never the problem; its file mode was.** `adb push` leaves
`titles.qcow2` mode 0644. The app reaches files in its `x1box` directory
through a group, so it can read the disk but cannot open it read-write.
`docs/testing/rollback_release.sh:89` recorded this on 2026-09-12 for
hdd.img: "adb push leaves 0644 and the app reaches those files through a
group, so it will report 'Could not open hdd.img: Permission denied' and then
crash in the GPU driver during teardown". `dev_push` in dispatcher.sh (#622)
never set the mode. `hdd_img_guard`'s reset pushes hdd.img through the same
`dev_push`, so the first hdd.img reset would have broken the disc runs the
same way.

The path, from the source:

1. `xemu_check_file()` (system/vl.c:2536) opens the HDD with `"rb"` only.
   A readable, unwritable disk passes, and `-drive
   index=0,media=disk,file=...,locked=on,cache=writethrough` is added
   (system/vl.c:3086).
2. `qemu_create_early_backends()` runs `qemu_display_early_init` (the
   `sdl2_display_early_init` log line), then `configure_blockdev()`
   (system/vl.c:2103). That opens the drive through `drive_init_func` with
   `&error_fatal`, so a read-write open that fails prints "Could not open
   ...: Permission denied" and calls `exit(1)`.
3. On Android that `exit` runs on the qemu thread while the main thread holds
   a current GL context. Teardown kills the process in the GPU driver:
   SIGSEGV at `si_addr=0x0` in `libGLESv2_adreno.so`, or
   `FORTIFY: pthread_mutex_lock called on a destroyed mutex` (signal 6).
   The stderr line never reaches logcat because the process is gone first.

There is no NULL-pointer bug in xemu's start-up. The NULL dereference is in
the Adreno driver during an `exit()` from another thread, a symptom of
teardown.

## Measured vs inferred

| claim | how | status |
|---|---|---|
| every early crash is on titles.qcow2, none on hdd.img | all Nova/Thor logcats 09-28 00:00 to 09-29 20:05: count `sdl2_display_early_init` followed by `Caught signal` before `qemu_init took` | **measured**: ~190 hdd.img runs, 0 early crashes; 11 titles.qcow2 runs, 10 died (21 of 22 starts) |
| the image's bytes are openable by qemu | desktop xemu (8d72e2d4af, `cloud-remediate-395/build-linux`, libibverbs stubbed) with `hdd_path` = a copy of `nova-52e09d0361a3.qcow2`: reaches "Failed to load BIOS", i.e. past `configure_blockdev` | **measured** |
| an unwritable HDD kills start-up at `configure_blockdev` | the same image, copy chmod 0444: `Could not open '...IMG.qcow2': Permission denied`, exit 1 | **measured** (desktop) |
| on the device the pushed file is 0644 and the app cannot write it | rollback_release.sh note (09-12, same symptom); `dev_push` has no chmod | **inferred**. The first proof run records `mode_found` in hdd.json, which measures it |
| the "170 MB image" | the SAME b634 disk after the one run that booted it (18:42, `1-1790724690-lane.ibcache-1390145`, qemu_init 869 ms) wrote to it: 9,961,472 -> 177,995,776 B, then 1b97.. -> a1d4.. -> 77d5.. as later runs wrote more. Not a seed, not app-made | **measured** (hdd.json sequence) |
| why the 18:42 start could write a 0644 disk | nothing in dispatcher.log 18:40:55-18:42:04 differs from the crashing runs (same title, same binary, plan keep) | **unexplained**. Something outside the dispatcher changed the file's mode or ownership; after that start, every run on that file booted until the 19:51 rebuild pushed a new 0644 file |

Timeline (Nova, from `results/*/hdd.json` and logcat):

| runs | disk | plan | starts | outcome |
|---|---|---|---|---|
| 18:36-18:41 (5) | b634.., 9.96 MB, pushed 18:36 | seed,build,keep / keep | 2 each, all died 2-7 ms after `sdl2_display_early_init` | VOID |
| 18:42 | b634.. | keep | 1, booted | ok, wrote 168 MB |
| 18:49-19:40 (3) | 1b97.. / a1d4.. / 77d5.., 178 MB | keep | booted | ok |
| 19:51-20:05 (6) | 52e0.., 10.2 MB, pushed 19:51 | build,keep / keep | 1-2 each, all died | VOID (the 20:05 one is not marked VOID but its app died before the route's first input) |

## The fix (docs/testing/dispatcher.sh)

- `dev_push` chmods the `.new` file to 660 before the rename and reads the
  mode back after it.
- `titles_disk_prepare` makes a KEPT disk 660 before every title run. The
  52e0 disk on the Nova now plans `keep` and would never be pushed again, so
  a push-only fix would have left it crashing. A disk that cannot be made 660
  fails the request before hddPath points at it. hdd.json gains `mode_found`,
  `mode` and `split_from`.
- A request's own env `HAKUX_TITLES_DISK` beats the worker's, in both
  directions (`split_from: request`). The worker's kill switch stays on for
  everyone else.

Not changed: `titlestate.py`, `saves.py` and `tools/make_xbox_hdd.py`. The
builder's output is a valid qcow2 v3 that qemu opens. The brief listed them
on the premise that a property of the image was at fault, and that premise is
refuted above.

## Selftest (selftest.d/99-hdd-split.sh)

The fake adb's `push` now leaves 0644, as the real one does, and a `nochmod`
switch makes chmod fail. New legs: the pushed disk is 660; a kept 0644 disk is
made 660 with its bytes unchanged and `mode_found` recorded; a disk that
cannot be made 660 fails the prepare with hddPath still on hdd.img; a request's
`HAKUX_TITLES_DISK=1` beats the worker's 0, a request naming none stays off,
and a request's 0 beats a worker's on; the reset hdd.img is 660.

Falsifier: with master's dispatcher.sh these legs go red (9 of 61, the modes
read 644). With this branch: 61 passed, 0 failed.

## The app-side refusal (brief step 3): not in this PR

The cheap version checks `access(hdd_path, R_OK | W_OK)` next to
`xemu_check_file` at system/vl.c:3080. It would queue the existing "Failed to
open hard disk image file" message and leave out the `-drive` instead of
exiting. That is an emulator start-up file, so it needs lane.local's grant:
a board request. The harness fix removes the cause without it. Attempt 2
did not file that request: the owner's offline scope ("limited lanes, stay
focused", 09-29) keeps this lane to the harness fix. It stays open for a
later lane.

## Device proof (brief step 5): after the fold

The worker runs `$DISPATCH_DIR/bin`, a snapshot of the dispatcher's master
tree, so neither the chmod nor the per-request override is live until #629
folds and the dispatcher tree is fast-forwarded. A proof request queued
before then would boot hdd.img and prove nothing. After the fold, three
requests on the Nova, in order:

    docs/testing/request.sh --who lane.hddcrash --device nova \
      --purpose "#397 hddcrash proof N/3: titles disk 660 + request override" \
      --title 56550003-Crash_Bandicoot_The_Wrath_of_Cortex.xiso.iso --route crash-wrath-of-cortex \
      --seconds 240 --env HAKUX_TITLES_DISK=1 --no-expect "harness proof, not an arm"

What each should show: run 1 plans `keep` on 52e0 (the bytes that crashed six
runs) with `mode_found` 644 and `mode` 660, `HDD from pref: .../titles.qcow2`
in logcat, `qemu_init took`, and the warp room hub in the route frames. If
Crash writes a save on NEW GAME, run 2 plans harvest, `build`, keep, and run 3
keeps the built sha. If it writes none, no build happens naturally. In that
case the build leg comes from the next title run that saves (a first-run
route, e.g. `midnight-club-3.first-run`).

## Do not repeat

- Do not compare qcow2 headers to explain this. The bytes are fine, and one
  run booted the very same file.
- A crash within ms of `sdl2_display_early_init` with a GPU-driver PC is an
  `exit()` from `configure_blockdev`, not a display bug. Look for a drive
  that won't open.
- Anything pushed into `files/x1box` must be made 660 (dev_push does it now).

## Status 2026-09-29 ~20:40 PDT: blocked on GitHub

The fix and these NOTES are committed on `lane/hddcrash`, but only locally.
`git push` and every `gh api` call return 403 "Your account was suspended".
Only the lane's first commit reached PR #629 (draft). The fix commit, the PR
body update, the `[lane.hddcrash]` comments and the #397 post are all
waiting on account access. Once access is back: push, update the PR body
from `.git-prbody.md` (REST PATCH), wait for CI green, `gh pr ready 629`,
post on #397.

## Attempt 2, 2026-09-29 ~22:30 PDT: why attempt 1 did not finish

Attempt 1 finished the fix and the NOTES, then stopped: from ~21:00 PDT
GitHub suspended the account, so the push, the PR body update, the ready
mark and the #397 post all returned 403. Nothing was wrong with the work.

Attempt 2 follows lane.local's offline protocol: `origin` is the local
stand-in, the PR is `docs/lanes/hddcrash/PR.md`, the #397 post is
`OUTBOX.md`. master had not moved (0 behind), so no merge was needed.
Local checks run in place of CI are listed in PR.md.

The device proof still waits on the fold, for the reason above: the worker
runs `$DISPATCH_DIR/bin`, a snapshot of master, so a proof request queued
now would boot hdd.img and prove nothing. The Nova is also on the owner's
top-up hold. After the fold and the dispatcher update, the three requests
in "Device proof" are the next step, then tell lane.local to remove the
drop-in.

## Attempt 3, 2026-09-29 ~22:40 PDT: why attempt 2 did not finish

Attempt 2 pushed PR.md and OUTBOX.md but left `State: draft` because the
full `selftest.sh` was still running. That run was a background task of
the session, so it died when the session ended. `scratch/selftest-full.log`
stops at dispatch-hardening E2 and has no total. Attempt 3 re-runs the full
selftest in shards (`SELFTEST_SHARD=k/n`), detached with `setsid nohup`
into `scratch/selftest-shard-*.log`, and polls those logs in this session.
master has not moved (0 behind).

Result: the full selftest could not finish in this session either. The host
sat at load ~260 and its clock nearly stopped: a 540-second poll loop
returned after 1-4 s of `/proc/uptime`. The four shards finished 29 of 116
fragments with 0 FAIL. Attempt 2's partial run covers the arms chain and
51-dispatch-hardening A-E2, with 0 FAIL. 99-hdd-split alone passed 61/0.
PR.md lists them and is set `State: ready`. The full selftest.sh is
`offline_fold.py`'s gate at fold time. If that gate finds a red, the
shard logs are `scratch/selftest-shard-{0..3}.log` in this worktree
(untracked; the shards were left running).

Next, unchanged: after the fold and the dispatcher update, the three Nova
proof requests in "Device proof", then tell lane.local to remove the drop-in.
