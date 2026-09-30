# hddcrash: titles disk mode 660; a request's HAKUX_TITLES_DISK wins (#397)

State: ready

Lane: hddcrash            Issue: #397
Base: master @ a3681ccb0b0eb2cc445fd59dc501473f51b8ce92
Files: docs/testing/dispatcher.sh, docs/testing/jobs/selftest.d/99-hdd-split.sh, docs/lanes/hddcrash/NOTES.md, docs/lanes/hddcrash/PR.md, docs/lanes/hddcrash/OUTBOX.md
Prediction: none: no arm (a harness fix; the proof is a title soak, after the fold)
Needs device: yes    Needs NDK: no

Release note (none): harness title-disk builder

## Cause: the disk's file mode, not its bytes

`adb push` leaves `titles.qcow2` at mode 0644. The app reaches files in `files/x1box` through a group, so it can read the disk but not open it read-write. `rollback_release.sh:89` documented this failure for hdd.img on 09-12. #622's `dev_push` never set the mode.

What happens at start-up:
1. `xemu_check_file` (system/vl.c:2536) only opens the disk `"rb"`, so the `-drive` is added.
2. `configure_blockdev` (system/vl.c:2103, `&error_fatal`) fails with "Could not open ...: Permission denied" and calls `exit(1)` on the qemu thread.
3. The render thread still holds GL, so the process dies in `libGLESv2_adreno.so` (SIGSEGV, `si_addr=0x0`) or on "pthread_mutex_lock called on a destroyed mutex". That happens 2-7 ms after `sdl2_display_early_init`, before stderr reaches logcat.

There is no NULL bug in xemu itself.

| evidence | result |
|---|---|
| early crashes, all Nova/Thor logcats 09-28 00:00 to 09-29 20:05 | hdd.img: ~190 runs, 0. titles.qcow2: 10 of 11 runs died (21 of 22 starts) |
| desktop xemu 8d72e2d4af, hdd = copy of `nova-52e09d0361a3.qcow2` | opens it: gets past `configure_blockdev` to "Failed to load BIOS" |
| the same copy at mode 0444 | `Could not open '...': Permission denied`, exit 1 |
| the "170 MB image" | the same b634 disk after the one run that booted it (18:42) wrote 168 MB to it |

The builder (`saves.py` / `titlestate.py` / `make_xbox_hdd.py`) is unchanged: its output is a valid qcow2 that qemu opens.

## Fix (dispatcher.sh)
- `dev_push` sets 660 on the `.new` file before the rename and reads the mode back. This also covers `hdd_img_guard`'s hdd.img reset, which pushes through the same function.
- `titles_disk_prepare` makes a **kept** disk 660 before every title run. This is needed because 52e0, the disk now on the Nova, plans `keep` and would never be pushed again. If the disk can't be made 660, the request fails before hddPath is set. hdd.json now records `mode_found`, `mode` and `split_from`.
- A request's own env `HAKUX_TITLES_DISK` beats the worker's kill switch, in both directions.

## Selftest
New legs in 99-hdd-split. The fake push leaves 0644, as the real one does. The legs cover:
- the pushed disk is 660;
- a kept 0644 disk is repaired, with its bytes unchanged;
- a chmod failure fails the prepare;
- the override works in both directions;
- the reset hdd.img is 660.

Results: 61 pass on this branch. Against master's dispatcher.sh, 9 of them fail.

## Local checks (no CI while GitHub is suspended)

- `SELFTEST_ONLY=99-hdd-split docs/testing/jobs/selftest.sh`: 61 passed, 0 failed.
- full `docs/testing/jobs/selftest.sh`: **incomplete, 0 FAIL in what ran.** On 09-29 ~22:30-23:00 PDT the host sat at load ~260
  and the fragments crawled: four `SELFTEST_SHARD=k/4` shards, detached, finished 29 of 116 fragments with 0 FAIL
  (10-arms-list, 55-affinity-offpool, 56-desktop-worker, 57-vsh-disc, 58-pull-verify, 65-*, 66-*, 67-status-measured,
  70..76-cloud/fold/nv2a/pr-sweep/x1a7, 79-stop-hook-hold, 80-labels, 84-perf-regimen, 85-fold-ci, 86/87-nightly, 87-fold-stale-ci,
  88-sweep-cover). Attempt 2's whole run got through the arms chain 10..50 and 51-dispatch-hardening A-E2 (52 ok, 0 FAIL)
  before it died. The fragments that drive dispatcher.sh, where the change is, are 99-hdd-split and 51-dispatch-hardening,
  plus the arms chain. All of those ran green. The rest of the full run is left to `offline_fold.py`'s selftest.sh gate.

## Device proof: after the fold

Not in this PR. The worker runs `$DISPATCH_DIR/bin`, a snapshot of master, so the chmod and the per-request override are not live until this folds and the dispatcher tree is updated. After that, the three Nova requests listed in NOTES.md "Device proof" run, and lane.local removes the `titlesdisk-off.conf` drop-in once they are green.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
