# Audit pass 2 -- PR #627 lane/hddperm (#397)

Head audited: `c817b59a59`. Remediation commit: `c817b59a59` (same head --
the remediation is the tip). Verifying each pass-1 scenario in
`2026-09-29-hddperm-pass1.md` can no longer occur.

Verdict: **clean -> fold-ready.**

## M1 -- the mode is verified after the rename, so a failed check has already exposed the disk

Fixed. `dev_push` (dispatcher.sh:589-600) now reads `dev_mode "$dst.new"`
*before* the `mv`, and only renames once the group digit is `[67]`. A chmod
that exits 0 without taking is caught on `<path>.new`; the rename that would
have exposed the read-only disk never runs, and `$dst` is untouched.

Confirmed the scenario itself, not just the diff: added leg
`chmodnoop` in `99-hdd-split.sh` -- a fake chmod that exits 0 and leaves the
file at 644 -- runs `dev_push` against `hdd.img` the same way the pass-1
scenario describes (HDD guard resetting an oversize disk). Ran it directly:

```
env SELFTEST_ONLY="99-hdd-split.sh" bash docs/testing/jobs/selftest.sh
```

`ok a chmod that does not take fails dev_push (rc=1)`, `... hdd.img is the
disk it was`, `... still 660 (got: 660)` -- the reset disk never replaced the
good one. All 59 legs pass, 0 failed (up from 53 pre-remediation, since two
new legs were added: the M1 leg above and its `.new` cleanup assertion).
The rename now happens only after the mode check, so the ordering that let a
`chmod`-exits-0-but-ignored device replace a good disk with a 644 one no
longer exists on this code path -- confirmed by reading dispatcher.sh:589-600
and by the leg exercising exactly that device behaviour against the real
function, not a mock of it.

## L1 -- a failed push leaves `<path>.new` on the device

Fixed. Every return path in `dev_push` before the rename now goes through
`dev_push_fail()`, which `rm -f`s `$1.new` on the device before logging and
returning 1: adb-push failure, sha mismatch, chmod failure, and the new mode
check failure all call it. Selftest legs assert `hdd.img.new` is removed on
both the `nochmod` leg and the new `chmodnoop` leg (`... and hdd.img.new is
removed`, both green). The post-rename sha-mismatch return does not need
this (`$dst.new` no longer exists once the rename has succeeded).

## L2 -- the group-writable test accepts write-without-read

Fixed. The regex is now `[[ "$mode" =~ [67].$ ]]`, requiring the group digit
to be 6 or 7 (read+write), not merely one of `2367`. Read at
dispatcher.sh:597-598 with the comment explaining why (xemu opens the disk
read-write).

## L3 -- NOTES line numbers

Fixed. The NOTES caller table now reads `646` / `750` with no `~`, and the
current dispatcher.sh has `dev_push "$img" "$dpath"` at line 646 and
`dev_push "$sdir/hdd.img" "$dpath"` at line 750 -- checked directly against
the file, not against the commit message.

## Not re-checked

"Not findings" from pass 1 (`dev_mode`'s 4-digit regex, the fake adb's stat
mapping, the refused-chmod leg's `cp -p` restore) named no defect and this
PR's remediation did not touch that code; nothing to re-verify.

## Method

Read the remediation diff (`git show c817b59a59`) against each pass-1
scenario, then read the current `docs/testing/dispatcher.sh` and
`docs/testing/jobs/selftest.d/99-hdd-split.sh` directly (not just the diff)
to confirm the fixed ordering is what ships. Ran the fragment in isolation
(`SELFTEST_ONLY=99-hdd-split.sh`) rather than trusting the CI-green claim in
the PR: 59 passed, 0 failed.
