# lane.verdict433 outbox

Offline protocol (GitHub suspended ~2026-09-29 21:00 PDT): issue posts
accumulate here instead of going to `gh issue comment`. lane.local relays a
summary per issue after reinstatement.

## #433 -- 2026-09-30 05:20 UTC

Session 7's batch-4 results are in: **two new Playable titles, both on the
Nova at the default confirmation regimen.**

- **KOF: Maximum Impact - Maniax** -- PASS Playable, fps_ok=0.9936,
  gameplay 1282.6s, no crash/hang, audio_short=0.0005, 0.1121 J/frame.
- **Azurik: Rise of Perathia** -- PASS Playable, fps_ok=0.9521, gameplay
  1292.3s, no crash/hang, audio_short=0.0, 0.228 J/frame. (This is the same
  title that FAILED its Thor confirmation on heat in session 2 --
  moving heat-sensitive confirmations to the Nova per your 12:00 PDT
  addendum is what turned it Playable.)

The other four in the batch did not read clean verdicts, for two different
reasons, neither of them a real fps/crash finding:

- **WWE Raw 2** and **50 Cent: Bulletproof** voided on a harness bug:
  `titles.qcow2` (the shared Nova HDD file) was pushed with `adb push`'s
  default `rw-r--r--`, one group-write bit short of what xemu needs to open
  it -- same bug as PR #627/lane.hddperm, #397. hostops root-caused it
  mid-batch and already re-queued both (`-1456493r2`, `-1456544r2`); this
  lane did not queue a third attempt.
- **007: Agent Under Fire** hit the same bug from the other side: its run
  started just before hostops's interim chmod-660 fix landed, and instead
  of voiding cleanly it hung silently at `qemu_init` for the full 1475s
  timeout (no crash line, nothing in logcat after `sdl2_display_early_init`
  until the timeout). Not a read on the title -- rerun queued
  (`-366094`).
- **Baldur's Gate: Dark Alliance** booted clean (after the fix) and played
  its full route into gameplay for 1684 of 1760 planned seconds (1190s of
  gameplay, 10s short of the 1200s bar) before an adb capture flake aborted
  the soak. No crash, no hang, no low-fps reading -- a single-run device
  flake this close to the bar. Rerun queued (`-366130`).

Full detail, including the tier A/B/C ranking and prior sessions' work, is
in `docs/lanes/verdict433/NOTES.md` on this branch.

**Note on process:** GitHub returns 403 for this account as of last night,
so this post and the PR body are landing in `docs/lanes/verdict433/` per
the offline protocol addendum instead of `gh issue comment` / `gh pr`.

**Waiting on:** the two reruns just queued (`-366094`, `-366130`) and
hostops's two r2 requeues (`-1456493r2`, `-1456544r2`), all on the Nova,
each 20-30 min once running. Not polling from inside this session per the
offline protocol's scope note -- parking here for the next resume.
