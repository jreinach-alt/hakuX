# lane.devpushro1018 -- NOTES (#433)

Brief: `dev_push`'s mode-660 check blocks every disc push to the Nova's SD card
(`DEVICE_ISO_ROOT`). Give it a read-only mode that skips the 660 step for a
disc, while every read-write caller (titles.qcow2, the hdd-guard push) keeps
the existing requirement.

## 0. Already tried

| Who | What | Result |
| --- | --- | --- |
| lane.hddcrash (#622) | wrote the titles-disk mode-660 rule itself: `adb push` leaves a file 0644, the app can read but not open it read-write, and an unopenable `-drive` kills the qemu thread while the render thread holds GL (dispatcher.sh:801-812). | Correct for titles.qcow2 and the hdd-guard push, which both live in the app's internal x1box directory and are opened read-write. Wrong for a disc on the SD card. |
| lane.dispatchpush1018 (#433, folded 127cf0f2c1) | fixed `dev_push`'s source-path argument (`wslpath -w`) so `adb.exe` can open a `/mnt/d` or `/home` source at all. | Fixed the push itself; uncovered the *next* failure at the mode-660 step once the push and sha check started succeeding. |
| lane.mkdawhite1018 (#1058, NOTES.md section 7.1) | traced request `1792345978-mkdawhite1018-1601447`'s `title not on device` ERROR to `dev_make_660` failing on the disc push: the SD card's mount synthesizes file modes, `chmod 660` is a no-op there, and the mode always reads back 770 -- which the titles-disk rule, applied unconditionally by `dev_push`, refuses even though xemu opens a disc read-only and 770 is fine. Drafted the lever: an optional `ro` third argument to `dev_push` that skips `dev_make_660` and the final mode check. | Correct root cause and lever; this lane implements it. Did not touch `dev_push` itself -- outside its own `Files:`, escalated to lane.local (unreachable 4.5h / 13+ ticks) and then to hostops, which briefed this lane directly. |

This lane's own work: verified the draft lever against the current
dispatcher.sh (line numbers had drifted slightly -- `dev_push` is now at
:1043 after dispatchpush1018's `wslpath` fix added a line, the call site at
:1249 -> :1260 after this lane's own comment block), applied it, added the
selftest fragment the brief asked for, and ran it in isolation plus together
with the fragments that already exercise `dev_push` and `dev_make_660`
(`99-dev-push-wslpath`, `99-hdd-split`, `85-savestate`, `98-dispatch-doctor`,
`99-iso-roots`) before the full `selftest.d` suite.

## 1. The fix

`dev_push` (dispatcher.sh:1037-1066) takes an optional third argument `ro`.
When set: the sha check after the push still runs, but `dev_make_660` and the
final `dev_mode "$dst" = 660` check are both skipped. `ensure_title_staged`'s
one disc-push call site (dispatcher.sh:1260, inside the function that also
backs the dispatch doctor's `fix push-iso` retry) now passes `ro`. The other
two `dev_push` callers -- titles.qcow2 (:1680) and the hdd-guard push
(:1813) -- are unchanged and still require 660, per dispatcher.sh:801-812
("THE DISK MUST BE MODE 660"), which stays correct for a disk the app opens
read-write.

## 2. Selftest fragment

`docs/testing/jobs/selftest.d/99-dev-push-ro-disc.sh` (new). A fake `adb`
whose `shell` case special-cases `chmod 660 ...` as a no-op and `stat -c %a
...` as always answering `770` -- standing in for the SD card's mount, which
ignores `chmod` the same way. Two legs:
- a disc push (`dev_push ... ro`) succeeds under it, sha-verified;
- a titles-disk-style push (no `ro`) still fails the same way it does
  today, and the destination is never written (the failure is caught before
  the rename).

Ran alone (`SELFTEST_ONLY="99-dev-push-ro-disc"`): 2 passed, 0 failed.
Ran together with the other `dev_push`/`dev_make_660` fragments
(`SELFTEST_ONLY="99-dev-push-wslpath 99-hdd-split 85-savestate
98-dispatch-doctor 99-iso-roots"`): 188 passed, 0 failed -- no regression in
the read-write path these fragments already cover.

Full `docs/testing/jobs/selftest.sh` (no SELFTEST_ONLY, all 153 fragments):
3732 passed, 1 failed. The host was running several other lanes' and CI's
own selftest.sh concurrently while this one ran, so each full run took
40-60+ minutes against the script's own 18-25 min comment; this lane waited
it out in the foreground rather than end the session on a job of its own.

The one failure is `66-status-titles.sh`'s `check --pages passes when every
page agrees...`: `title_registry.py check --pages` reports "PAGE README.md:
the Playable line is not the numberless form home_page.py rewrites" on both
the agreeing and the mutant fixture, so the falsifier never reaches its own
assertion. **Pre-existing and out of this lane's scope**, not caused by this
fix: this lane's `git diff` touches only `dispatcher.sh` (the `ro` argument)
and two new files; nothing here touches README.md, home_page.py,
promotion_check.py, title_registry.py, or 66-status-titles.sh itself.
Reproduces alone (`SELFTEST_ONLY="66-status-titles"`, 21 passed, 1 failed)
with no other fragment involved, so it is not cross-fragment state. Per the
brief's instruction to touch an existing fragment only if it fails "for a
real reason" and to say so rather than fix it: said so here, left the
fragment and README.md untouched -- a README/home_page.py drift is a
different lane's fix (promotion surfaces, [[promotion-needs-every-surface]]
in memory), not a dev_push/disc-mode one.

## 3. Deploy

The host dispatcher runs its own snapshotted copy at
`/home/justin/hakux-work/dispatch/bin/dispatcher.sh`, refreshed by
`host-tools/dispatcher_update_window.sh` after this folds. This lane did not
run that script and did not hand-edit the live copy -- hostops owns the
update window once the fold lands.

## 4. What unblocks

mkdawhite1018's request `1792345978-mkdawhite1018-1601447` (Mortal Kombat:
Deadly Alliance, route `mkda-arcade`) is the one this fixes for. This lane
did not re-queue it and did not touch the Nova -- that is mkdawhite1018's own
request to resume once this PR folds and the dispatcher is updated.

## Questions

None open.
