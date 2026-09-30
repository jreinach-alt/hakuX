# lane.hddperm -- dev_push leaves a pushed disk 644 (#397)

## The read

`dev_push()` (docs/testing/dispatcher.sh) did `adb push src dst.new`, a sha
check, `mv -f dst.new dst`, a sha check, and never set a mode. `adb push`
creates the file as `shell` under umask 022, so the disk lands `rw-r--r--`.
The app (`u0_a145`) reaches files/x1box through the `ext_data_rw` group; every
file it made itself is `rw-rw----`. A 644 disk is read-only to it, xemu's
writable `-drive` open fails (`Could not open '.../titles.qcow2': Permission
denied`), the `:xemu` process aborts 0.2 s after start, and the dispatcher
records the downstream symptom, `not-foreground`.

`dev_push` has exactly two callers (read, `grep -n dev_push`; no other
`adb push` in dispatcher.sh):

| caller | line (after this PR) | pushes | first hit |
|---|---|---|---|
| `titles_disk_prepare`, `build` | ~634 | `titles.qcow2` | Nova, 2026-09-29 18:36 PDT, the first build since PR #622 |
| `hdd_img_guard`, reset | ~738 | `hdd.img` | not yet; would make every disc run crash too |

Both go through the one function, so the one fix covers both; the guard-reset
leg of the selftest asserts it.

## The fix

`dev_push` now `chmod 660`s `<path>.new` after its sha check and before the
rename, so the rename never exposes a read-only disk; a failed chmod fails the
push and replaces nothing. After the rename it reads the mode back
(`dev_mode`, `stat -c %a`) and fails unless the group digit has the write bit,
then checks the sha as before, and logs
`pushed <path> (sha256 <12>, mode <mode>)` to dispatcher.log.

The mode check is on group-writability, not `= 660`: a storage layer that
reports a wider mode the app can still write must not fail a good push.

## Selftest (99-hdd-split.sh)

The fake adb's `push` now leaves the file 644, as adb does, and the fixture
hdd.img is 660, as the app makes it. New legs:

- the first run's pushed titles.qcow2 is 660, as hdd.img is
- the rebuilt titles.qcow2 on the second run is 660
- the guard-reset hdd.img is 660, not adb push's 644
- a device that refuses the chmod fails `dev_push`, and hdd.img is unchanged

Falsifier: master's dispatcher.sh with the new fragment, 48 passed / 5 failed,
exactly the five new legs (`got: 644` on the three mode legs; `rc=0` and a
replaced hdd.img on the refused-chmod leg). This branch: 53 passed, 0 failed.

## Real-device proof: after the fold, not before

The dispatcher that serves requests runs from the host's DISPATCH_TREE
(master), not from a lane's ref, and lanes may not touch a device outside
request.sh, so no request can exercise this `dev_push` on a device before it
folds. Brief step 4 is therefore a post-fold check, and it is not done here.

What it looks like when it happens: the first title run whose plan is `build`
after the fold writes to dispatcher.log

    titles disk: build (...)
    pushed .../x1box/titles.qcow2 (sha256 ..., mode 660)
    titles disk: keep (...)

and its run has no `Permission denied` in logcat and no `not-foreground`
abort. A push that could not set the mode logs `push ...: chmod 660 failed`
or `mode is '644', not group-writable` and fails the request as
`TITLES DISK: push failed`, not as a void run.

State at 2026-09-29 ~19:00 PDT (read-only, titlestate registry):

- Nova: titles.qcow2 was chmodded by hand at 18:41; a run harvested it at
  18:48. `wanted(st) == image.built_from`, so the next plan is `keep` and no
  push happens until a run changes a save. The first rebuild after that on
  master's dispatcher lands 644 again and crash-loops.
- Thor: no titles.qcow2 yet; its first title run builds and pushes. Out of
  service (fan) today.

## For the next lane

- A fixture that stands in for a device must reproduce the device's modes, not
  only its bytes: the old fake push was `cp`, which kept the host file's mode,
  so the selftest could not see this.
- Do not re-chmod by hand as a fix; after this folds, the push sets it.
