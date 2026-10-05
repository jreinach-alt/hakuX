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
| `titles_disk_prepare`, `build` | 646 | `titles.qcow2` | Nova, 2026-09-29 18:36 PDT, the first build since PR #622 |
| `hdd_img_guard`, reset | 750 | `hdd.img` | not yet; would make every disc run crash too |

Both go through the one function, so the one fix covers both; the guard-reset
leg of the selftest asserts it.

## The fix

`dev_push` now `chmod 660`s `<path>.new` after its sha check, reads the mode
back on `<path>.new` (`dev_mode`, `stat -c %a`), and only then renames it
(the rename keeps the mode). A chmod that fails, or exits 0 and does not take,
fails the push with the old disk still in place and `<path>.new` removed
(pass-1 M1, L1). After the rename it checks the sha as before and logs
`pushed <path> (sha256 <12>, mode <mode>)` to dispatcher.log.

The mode check is on the group digit being 6 or 7 (read and write; xemu opens
the disk read-write), not `= 660`: a storage layer that reports a wider mode
the app can still use must not fail a good push.

## Selftest (99-hdd-split.sh)

The fake adb's `push` now leaves the file 644, as adb does, and the fixture
hdd.img is 660, as the app makes it. New legs:

- the first run's pushed titles.qcow2 is 660, as hdd.img is
- the rebuilt titles.qcow2 on the second run is 660
- the guard-reset hdd.img is 660, not adb push's 644
- a device that refuses the chmod fails `dev_push`, hdd.img is unchanged,
  and hdd.img.new is removed
- (pass-1 M1) a chmod that exits 0 and leaves 644 fails `dev_push`; hdd.img
  is unchanged and still 660, hdd.img.new is removed, the log names `644`

Falsifier: master's dispatcher.sh with the new fragment, 48 passed / 5 failed,
exactly the five new legs (`got: 644` on the three mode legs; `rc=0` and a
replaced hdd.img on the refused-chmod leg). Remediation: the pass-1 head's
dispatcher.sh with the remediated fragment, 56 passed / 3 failed -- the M1
leg's hdd.img replaced and 644, and the refused-chmod leg's hdd.img.new left.
This branch: 59 passed, 0 failed.

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
or `mode is '644', not group read-write; <path> left as it was` and fails the request as
`TITLES DISK: push failed`, not as a void run.

State at 2026-09-29 ~19:00 PDT (read-only, titlestate registry):

- Nova: titles.qcow2 was chmodded by hand at 18:41; a run harvested it at
  18:48. `wanted(st) == image.built_from`, so the next plan is `keep` and no
  push happens until a run changes a save. The first rebuild after that on
  master's dispatcher lands 644 again and crash-loops.
- Thor: no titles.qcow2 yet; its first title run builds and pushes. Out of
  service (fan) today.

## Attempt 2 (2026-09-29 PDT): CI red on e9e62ee32e, a fixture umask

Why attempt 1 did not finish: its head passed the audit and every local run,
but `selftest (2)` on CI failed one leg, `a chmod that does not take ...
still 660 (got: 640)`. Attempt 1 ran the fragment only on this host, whose
umask is 002, and never under the runner's 022.

The cause is the fixture, not `dev_push`. Read: `dev_push` chmods and stats
only `<path>.new` before the rename and never touches `<path>` on a failure.
The refused-chmod leg saved `hdd.img` with a plain `cp` to `hdd.before`, which
created the copy at 660 & ~umask, so 640 on CI, and then restored it over
`hdd.img` with `cp -p`. That left a 640 `hdd.img` at the start of the "does
not take" leg. Reproduced here with
`SELFTEST_ONLY=99-hdd-split` under `umask 022`: 58 passed, 1 failed, the same
line. With the save done as `cp -p`: 59 passed, 0 failed under umask 022.
No assertion changed.

## Attempt 3 (2026-10-04 PDT): superseded on master; merged down to the increment

Why attempt 2 did not finish: its CI fix (7f98648c69) was pushed after
GitHub suspended the account (09-29 ~21:00 PDT), and the offline protocol's
`docs/lanes/hddperm/PR.md` was never written, so foldqueue never saw a
`State: ready` and the branch sat unfolded holding dispatcher.sh. Meanwhile
lane.hddcrash folded the same fix to master (9b274b6be3, 09-29 20:27 PDT):
`dev_make_660` on `<path>.new` before the rename, read back, and a prepare
that repairs a *kept* 0644 titles disk (#622's disks planned `keep` and were
never pushed again, so a push-only fix could not reach them). The branch was
714 commits behind and conflicted on both code files.

Resolution: merge origin/master, take master's `dev_push`/`dev_make_660` and
master's fragment whole, and keep only what this lane had that master lacks:

- `dev_push` removes `<path>.new` on every failure before the rename (pass-1
  L1). Master's left a stale `.new` (a full disk image) on the device.
- the fake adb's `chmodnoop` (chmod exits 0 and does nothing), and a
  push-level leg for each of `nochmod` / `chmodnoop`: dev_push fails,
  hdd.img's bytes and mode are unchanged, hdd.img.new is removed, the log
  names the mode the chmod left. Master tests a refused chmod only through
  the prepare's kept-disk path.

Dropped as duplicated by master: this lane's `dev_mode`, its group-digit
`[67]` check (master requires exactly 660; I kept master's), and its 660
legs on the pushed/rebuilt/reset disks (master has the same legs).

| run (SELFTEST_ONLY=99-hdd-split) | result |
|---|---|
| this branch, umask 022 | 72 passed, 0 failed |
| this branch, umask 002 | 72 passed, 0 failed |
| falsifier: master's dispatcher.sh + this fragment, umask 022 | 70 passed, 2 failed: the two `hdd.img.new is removed` legs |

Real-device proof (brief step 4): master's fix has been live since its fold.
This branch's increment touches only the failure path, which no healthy
device takes, so it gets no device run.

## For the next lane

- Run a mode-asserting selftest under `umask 022` before pushing: the host is
  002, CI is 022, and a plain `cp` in a fixture makes the two disagree.

- A fixture that stands in for a device must reproduce the device's modes, not
  only its bytes: the old fake push was `cp`, which kept the host file's mode,
  so the selftest could not see this.
- Do not re-chmod by hand as a fix; after this folds, the push sets it.
