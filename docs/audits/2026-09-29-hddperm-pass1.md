# Audit pass 1 -- PR #627 lane/hddperm (#397)

Head audited: `ca3a7152a1`. Diff: `docs/testing/dispatcher.sh` (`dev_mode`,
`dev_push`), `docs/testing/jobs/selftest.d/99-hdd-split.sh`,
`docs/lanes/hddperm/NOTES.md`. CI green on this head (build x2, selftest 0-3).

Verdict: **1 MEDIUM, 3 LOW -> needs-remediation.**

The diagnosis holds: `dev_push` is the only push path in dispatcher.sh
(callers at 639 `titles_disk_prepare` and 743 `hdd_img_guard`), and chmod on
`<path>.new` before the rename is the right place for the fix. The fake adb now
reproduces adb push's 644, so the selftest can see the bug (the falsifier in
NOTES: 5 new legs red on master's dispatcher).

## M1 -- the mode is verified after the rename, so a failed check has already exposed the disk

`dev_push` (dispatcher.sh:589-595) runs `chmod 660 .new`, then `mv -f .new dst`,
and only then `dev_mode "$dst"` and the group-write check. The only thing the
chmod leg catches before the rename is a chmod that *exits non-zero*. The
read-back exists for the other case, a chmod that exits 0 without the mode
taking (a storage layer that derives or ignores modes, which is what the
comment's "a storage layer that reports a wider mode" reasoning already
allows for). In that case the check fires after the 644 disk has replaced
the good one.

Failure scenario (hdd.img leg): the HDD guard resets an oversize hdd.img on a
device where `chmod 660` returns 0 and leaves 644. `mv` replaces hdd.img with
the 644 reset disk; `dev_mode` reads `644`; `dev_push` returns 1;
`guard_fail` logs `HDD GUARD ALERT: push of the rebuilt disk failed ...;
hdd.img left as it was` and deletes `$sdir/hdd.img`. hdd.img was *not* left as
it was. It is now the reset disk, read-only to the app, so every disc run
aborts with `Permission denied` / `not-foreground`, which is the crash-loop
this PR exists to prevent, now on the disc side, under a log line that says
nothing changed. The same ordering also makes a transient `stat` timeout
(30 s `ADB_QUICK_TIMEOUT`) after a good rename report a replaced disk as
untouched.

The comment at 583-584 ("the mode is set on <path>.new, so the rename never
exposes a read-only disk") states the property the code does not have.

Fix: read `dev_mode "$dst.new"` and apply the group-write check *before* the
`mv` (rename preserves the mode), failing without replacing anything; keep a
post-rename sha check as now. Add a selftest leg where the fake `chmod` exits
0 and does nothing, asserting that `dev_push` fails and hdd.img is unchanged.
The existing `nochmod` leg only covers the exit-1 case.

## L1 -- a failed push leaves `<path>.new` on the device

On the chmod-failure path (and the new mode-failure path) `dst.new` is not
removed. For titles.qcow2 that is a full disk image left in files/x1box. The
selftest's refused-chmod leg `rm`s `hdd.img.new` itself, which shows it is
left. The sha-mismatch path already behaved this way before this PR, so this is
not a regression. A `rm -f '$dst.new'` on each failure return would fix it.

## L2 -- the group-writable test accepts write-without-read

`[[ "$mode" =~ [2367].$ ]]` passes a group digit of 2 or 3 (`-w-`, `-wx`).
xemu opens the disk read-write, so it needs group read too. `[67].$` states
the requirement. No realistic path produces 620 here, so this is LOW.

## L3 -- NOTES line numbers

The NOTES caller table gives `~634` / `~738`; the calls are at 639 / 743 on
this head. The `~` covers it. Noted only because pass 2 will read that table.

## Not findings

- `dev_mode`'s regex for 4-digit modes (setgid `2660`): the group digit is still
  second-to-last, so the check reads it correctly.
- The fake adb's `stat -c %a` goes through the `*) sh -c` arm with the path
  mapped, so the mode legs read the fixture file's real mode.
- The refused-chmod leg restores hdd.img with `cp -p` before the guard legs,
  so a red leg there does not cascade.
