# lane.dispatchpush1018 -- NOTES (#433)

The dispatcher's staged-disc push hands Windows `adb.exe` a `/mnt/d/...` source path, which it
cannot open. Every push of a title not already on the device fails identically, voiding the run.

## 0. Already-tried

| approach | where (commit/file) | verdict | what it means here |
|---|---|---|---|
| `dev_push` itself | dispatcher.sh:1043-1051 (`fa2e37531b`, lane.hddsplit, #397) | on master | Written for `titles.qcow2`, a `/home`-rooted source; never exercised against a `/mnt/d` source until `ensure_title_staged` started calling it with one (`6fa12571d1`). No wslpath conversion anywhere in it. |
| `ensure_title_staged` | dispatcher.sh:1211-1252 (`6fa12571d1`, dispatchdoctor1017 Section 1, "selftest green") | on master | Added the `/mnt/d` staging-root call into `dev_push` unchanged. The selftest that went green with it (`99-iso-roots.sh`) never runs the real `adb push` (section 2 below), so the gap shipped unseen. |
| titles-disk mode/perm fixes | `9b274b6be3`, `c817b59a59` (#397) | on master | Both touch `dev_push`'s mode-660 handling after the push, not the path handed to `push`. Unrelated to this fault. |
| profile-backup restore | `50ec1b82f6` (dispatchdoctor1017 Section 1c) | on master | Adds a `dev_push` *call site* (hdd.img rebuild), not a change to `dev_push` itself. Source is `$sdir/hdd.img`, host-side (`/home`), so it was never exposed to the `/mnt/d` gap either. |
| `git log --all -S wslpath -- docs/testing/dispatcher.sh` | n/a | **no hits** | `wslpath` has never appeared in this file. This is the first attempt at the fix, not a repeat of a prior one. |
| `git log --all -S dev_push` | n/a | listed above | No commit in `dev_push`'s history touches path form; all are mode/perm or call-site additions. |

No prior lane or commit attempted a `wslpath` fix for `dev_push`. The stop rule ("the same
failure twice for one cause means stop") does not apply: this is the first attempt.

### 0.1 AGENTS.md (the rule this violates)

AGENTS.md, "Disc images live on D:" section: `adb` here is the Windows `adb.exe`
(`/usr/local/bin/adb -> /mnt/c/platform-tools/adb.exe`). "Push from D:. ... Give it the Windows
path, `adb push "$(wslpath -w "$f")" <device path>`; it cannot stat `/mnt/d/...`." `dev_push`
did not follow this.

### 0.2 What `99-iso-roots.sh` can and cannot see

The existing selftest fragment (`docs/testing/jobs/selftest.d/99-iso-roots.sh`) drives a fake
`adb` whose `shell` subcommand runs the command against a local directory standing in for the
device (`IR_FS`). It exercises the *lookup* half of staging -- `device_title_path`'s multi-root
search, quoting, and the ERROR text -- by cutting the `local tpath ... fi` block out of
`dispatcher.sh` and running it against that fake. **It never calls `push`.** Its fake `adb`
script has no `push)` case at all; the staging *push* path (`dev_push`, `ensure_title_staged`'s
push branch) is not reached by this fragment, real or faked. That is exactly why the `/mnt/d`
path form was never caught: the one selftest that exercises staging does not touch the one
operation (`push`) that fails.

### 0.3 The failure, twice already, in dispatcher.log

- `dispatcher.log:29078/29094` (10-18 06:17): Halo's request `1792328946-haloring1017-2104088`
  staged `/mnt/d/hakux-staging/xiso/4D530004-Halo_Combat_Evolved.xiso.iso`, pushed, failed; the
  doctor's `push-iso` retried and failed identically 54s later (`dispatcher.log:29078-29085`,
  "DOCTOR: give-up: push-iso ran but the push ... failed").
- `dispatcher.log:29292/29294` (10-18 08:33-08:34): mkdawhite1018's request
  `1792337550-mkdawhite1018-3995143` staged `/mnt/d/hakux-staging/sweep/4D57000C-...xiso.iso`,
  pushed, failed the same way; the doctor's retry failed identically, then gave up ("the block
  is on the device/transport side").

Both sources are under `/mnt/d/hakux-staging/`. Both failures are `ensure_title_staged` ->
`dev_push` with an unconverted path. mkdawhite1018 (docs/lanes/mkdawhite1018/NOTES.md section 6)
did the full isolation: a non-device Windows-process test showed `\\wsl.localhost\...\mnt\d\...`
gives "Access is denied" while `D:\...` (the `wslpath -w` form) gives `True`, and traced both
dispatcher.log lines to the same cause. This lane does not repeat that isolation; it confirms
the same cause with the real `adb.exe` (section 1) and fixes it.

## 1. Confirmed with the real adb.exe (Nova, ee317437)

A small harmless file, `/mnt/d/hakux-staging/dispatchpush1018/scratch.txt` (57 bytes, one line),
pushed with the real `adb` (`/usr/local/bin/adb -> /mnt/c/platform-tools/adb.exe`) to a scratch
path on the Nova, then removed. One transfer per path form; no title disc involved.

| push source form | command | result |
|---|---|---|
| unconverted `/mnt/d/...` (today's `dev_push`) | `adb -s ee317437 push /mnt/d/hakux-staging/dispatchpush1018/scratch.txt /sdcard/Download/...` | `adb: error: cannot stat '/mnt/d/...': No such file or directory` -- the exact fault class in dispatcher.log |
| `wslpath -w` of the same file | `adb -s ee317437 push "D:\hakux-staging\dispatchpush1018\scratch.txt" /sdcard/Download/...` | `1 file pushed, 0 skipped` |
| `wslpath -w` of a `/tmp` source (stands in for `/home`) | `adb -s ee317437 push "\\wsl.localhost\Ubuntu\tmp\dispatchpush1018-home-scratch.txt" /sdcard/Download/...` | `1 file pushed, 0 skipped` |

The pushed file's on-device sha256 matched the source for the D: case
(`8a96debd2aade8361a015658dc68e2d85abe2f5343f3f433e88fdde80b0a9351`, both sides). Both device
copies were removed (`adb shell rm -f`) immediately after. The D: scratch directory was moved
aside and removed from this session's own `/tmp` (never `rm` on something not created by this
check; the directory existed only for this test). The Nova's `/storage/emulated` had 61 GB free
throughout (`df`), far above the 25 GB floor; nothing near that floor was touched. App data and
install state were never touched; nothing was uninstalled.

This confirms both halves mkdawhite1018 inferred from a non-device Windows process: the
unconverted `/mnt/d` path fails against the real device exactly as logged, and `wslpath -w`
fixes both a `/mnt/d` source and a `/home`-style source (so `titles.qcow2`'s existing call site
is unaffected).

After the fix (section 2), the *patched* `dev_push` function itself was exercised directly
(sourcing dispatcher.sh, `device_env ee317437`, then calling `dev_push` with a fresh
`/mnt/d/hakux-staging/dispatchpush1018/scratch2.txt`), not just a hand-typed `adb push`:
`dev_push` returned 0, the device file's sha256 matched the source
(`c506529b1ef...c53738621`, both sides) and its mode was 660 as `dev_push` requires before the
rename. Removed from the device and moved aside then removed from D: immediately after.

## 2. The fix

`dev_push` (dispatcher.sh) now resolves its host-path argument through `wslpath -w` before
handing it to `adb push`, instead of passing `$src` unchanged. One line change; the rest of
`dev_push` (the `.new`-then-rename, sha check, mode-660 check) is unchanged. All three call
sites (`ensure_title_staged`'s `/mnt/d` push, the titles-disk `build` push, the hdd-guard
rebuild push -- all `/home`-rooted except the first) go through the same converted path, so
none needed a separate change. No second fault appeared in the real push against the Nova
(section 1); nothing else in `ensure_title_staged` was touched. The second fault that *did*
appear was in three existing selftest fixtures, not the real device -- see section 3.1.

## 3. Selftest

`docs/testing/jobs/selftest.d/` gets one new fragment (see `Selftest:` in PR.md) that fails on
the pre-fix line. It stubs `adb` itself (real `adb.exe` is not available in CI and is a device
operation this fragment is not -- see "Never touch a device directly" in the lane contract);
what it does **not** stub is `wslpath`, which runs for real and must actually resolve a
`/mnt/d/...` source to a `D:\...`-style path and a `/home/...` source to a `\\wsl.localhost\...`
form. The fragment's fake `adb push` asserts its first argument is in one of those two forms and
fails loudly (not silently) if it sees an unconverted `/mnt/...` or bare `/home/...` string --
the exact bug this lane fixes. This is a different gap than `99-iso-roots.sh` (section 0.2),
which never calls `push` at all.

### 3.1 Second fault: three existing fixtures assumed `dev_push`'s old (unconverted) argument

`grep -rln '^\s*push)' docs/testing/jobs/selftest.d/*.sh` finds every fragment whose fake `adb`
implements `push` -- the only operation `dev_push`'s fix could affect. Four hits: this lane's
own `99-dev-push-wslpath.sh` (safe by construction, section 3), and three pre-existing fixtures
that all assumed their fake `push`'s source argument (`$2`, what `dev_push` hands `adb`) is a
literal path `cp` can open directly. Once `dev_push` started handing it a `wslpath -w`-converted
Windows-form string, each `cp` failed to find that string as a Linux path:

| fragment | line | fix |
|---|---|---|
| `99-hdd-split.sh` | 37 | `push) cp "$(wslpath -u "$2")" "$(map "$3")" ...` |
| `85-savestate.sh` | 32 | `push) cp "$(wslpath -u "$2")" "$(map "$3")" ...` |
| `98-dispatch-doctor.sh` | 59-62 | `cp "$(wslpath -u "$local")" "$dest"` (its push case names the arg `local` instead of positional `$2`, same fix) |

Each was confirmed with the stash A/B technique before touching it: dispatcher.sh's fix stashed
out (pathspec-limited to that one file, captured by SHA, restored with `git stash apply`, never
`pop`), the fragment run alone under `SELFTEST_ONLY`, clean every time at baseline (72/0, 27/0,
76/0 respectively) and failing only with the fix in place (34 failures in a combined run for
hdd-split; 15 of 27 for savestate; 2 of 78 for dispatch-doctor, in `fix push-iso` and
`diagnose retry`, both of which call `dev_push`/`push-iso` under the hood). `wslpath -u` round-
trips `wslpath -w`'s output exactly (verified separately, including paths with spaces), so this
is the same one-line class of fix as the production fix itself, not a new mechanism. All four
push-stubbing fragments run together after the fixes: 178 passed, 0 failed.

A full 150-fragment suite run was attempted to look for any further fallout outside the four
fragments the grep found; it did not finish inside a single command's time budget (5 of 150
fragments completed in ~580s with 0 failures before the budget ran out). The grep-based scan
is exhaustive for this change's blast radius -- `dev_push`'s fix can only affect a fixture that
fakes `push`, and there are exactly four, all accounted for above -- so this was not pursued
further.

## 4. Deploy (not done by this lane)

The host dispatcher runs its own copy, snapshotted from the fast-forwarded tree at
`/home/justin/hakuX` (confirmed identical to `docs/testing/dispatcher.sh` at this lane's base,
`1b3b3db8f4`) into `/home/justin/hakux-work/dispatch/bin/dispatcher.sh` whenever the dispatcher
restarts. That tree is brought to `origin/master` and the service restarted (which re-snapshots
`dispatch/bin`) by `host-tools/dispatcher_update_window.sh`, run after this lane's PR folds to
master -- not by hand-editing `dispatch/bin/dispatcher.sh`. This lane does not run it and does
not start or re-queue any Nova request beyond the one scratch-file push in section 1.

## 5. Status

Ready. Real-adb proof done (section 1), fix applied (section 2), selftest fragment added
(section 3), a second fault found and fixed in three pre-existing fixtures (section 3.1), deploy
path named for the fold (section 4). No second fault in the real device push; no device run
beyond the one scratch-file push.
