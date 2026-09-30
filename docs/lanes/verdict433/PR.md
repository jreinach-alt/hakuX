# lane.verdict433: measurement pass for #433 (0.5: 50 Playable)

State: draft

Lane: verdict433            Issue: #433 [#507]
Base: master @ 94cf8eb627 (branched); merged forward to 2c59b7bbba as of session 10 (already current with origin/master)
Files: docs/lanes/verdict433/NOTES.md, docs/lanes/verdict433/PR.md, docs/lanes/verdict433/OUTBOX.md, docs/lanes/verdict433/judge_copy.py, docs/lanes/verdict433/scan.py, docs/lanes/verdict433/soaks.py, docs/lanes/verdict433/sweep.py, docs/lanes/verdict433/queue_batch1.sh, docs/lanes/verdict433/queue_batch2.sh, docs/lanes/verdict433/queue_batch3.sh, docs/lanes/verdict433/queue_batch4.sh, docs/lanes/verdict433/queue_batch5.sh, docs/lanes/verdict433/queue_batch6.sh, docs/lanes/verdict433/queue_batch7.sh
Prediction: none: analysis-only (no emulator code changed; this lane only reads device results and queues confirmation soaks through the normal harness)
Needs device: yes (Nova; Thor confirmations withdrawn per lane.local's 2026-09-29 12:00 PDT addendum -- heat-sensitive work moved off the Thor pending #507)

## Summary

This lane's brief (#433, 2026-09-29 06:3x PDT): turn titles that already run
well into Playable verdicts, using the harness's normal confirmation
pipeline, and re-measure titles that this week's fixes moved. No emulator
code, Playable rule, or board file is touched -- this is a measurement-only
lane that reads `title_verdict.py` output and queues confirmation soaks via
`docs/testing/request.sh`.

Across nine sessions (2026-09-29 through 2026-09-30, each one queuing a
batch and stopping to let 20-30 min device soaks run rather than polling):

- **Five titles confirmed Playable this pass, all on the Nova at the
  default confirmation regimen:**
  - **KOF: Maximum Impact - Maniax** -- fps_ok=0.9936, gameplay 1282.6s, no
    crash/hang, audio_short=0.0005, 0.1121 J/frame.
  - **Azurik: Rise of Perathia** -- fps_ok=0.9521, gameplay 1292.3s, no
    crash/hang, audio_short=0.0, 0.228 J/frame. (This title FAILED its Thor
    confirmation on heat in session 2 -- `thermal-pause-F8` at +938s from a
    cool 48.6C start; moving it to the Nova per lane.local's addendum is
    what turned it Playable.)
  - **WWE Raw 2** -- fps_ok=0.9982, gameplay 1276.9s, no crash/hang,
    audio_short=0.0, 0.1357 J/frame.
  - **50 Cent: Bulletproof** -- fps_ok=0.9906, gameplay 1348.3s, no
    crash/hang, audio_short=0.0, 0.2498 J/frame.
  - **Baldur's Gate: Dark Alliance** -- fps_ok=1.0, gameplay 1303.9s, no
    crash/hang, audio_short=0.0, 0.1273 J/frame.
- **WWE Raw 2, 50 Cent and Baldur's Gate DA each needed a rerun first.**
  Their first attempts hit a harness bug: the shared `titles.qcow2` HDD
  file was pushed to the Nova with `adb push`'s default `rw-r--r--`
  permissions, one group-write bit short of what xemu needs to open it
  (root-caused by hostops mid-session, same bug as PR #627/lane.hddperm,
  #397). WWE and 50 Cent voided outright on this (hostops re-queued both);
  Baldur's Gate DA's original attempt instead ran 1684 of 1760 planned
  seconds before an adb capture flake aborted it 10s short of the bar. All
  three reruns, queued after hostops's interim chmod-660 fix, came back
  clean.
- **007: Agent Under Fire is not Playable.** Its first attempt started
  just before the chmod fix landed and hung silently at `qemu_init` for the
  full timeout (not a read on the title). Its rerun booted and played
  cleanly this time, but the generic survey route walks the character up to
  a vault-style door and then never gets past it -- the same camera angle,
  door and crosshair position recur at the 0-, 15- and 20-minute marks of
  the 20-minute window, a softlock against scenery, not gameplay (reviewed
  from `route-frames/`, `--reviewed-gameplay no`). AUF needs its own
  authored route before another confirmation is worth queuing; flagged for
  route-authoring lanes. (Also found and documented, not fixed: a gap in
  `title_verdict.py`'s `reviewed-gameplay no` handling that leaves
  `reached_gameplay` at "unconfirmed" instead of a reviewed "false" --
  doesn't change AUF's verdict, which is FAIL either way. See NOTES,
  session 9.)
- Three more Nova confirmations (Alien Hominid, 187: Ride or Die, Arctic
  Thunder) are queued and outstanding as of this write.
- Full ranking, tier A/B/C readings, and the session-by-session log (9
  sessions, including a harness anomaly where an entire batch of six
  queued requests vanished from the dispatch tree without a withdrawal or
  error record, root-caused as unrecoverable and simply re-queued) are in
  `docs/lanes/verdict433/NOTES.md`.

Release note (none): measurement/verification work only; no emulator code
changed.

## Local checks run (offline protocol -- no CI available)

- `python3 docs/testing/title_verdict.py <dir> --require confirmation
  [--reviewed-gameplay yes]` run directly against each of this session's
  six result directories; output captured in NOTES.md's table above.
- `git status` clean before and after this session's edits; only
  `docs/lanes/verdict433/*` files touched.
- No harness files (`docs/testing/*.py`, `docs/testing/jobs/*`) changed, so
  `docs/testing/jobs/selftest.sh` was not required per the offline
  protocol's fold checklist.

## Outstanding before ready

- Batch 6's Alien Hominid request (`-3086847`) is DONE but **voided**: it
  was re-pinned from the Nova to a Thor cold-start slot by lane.local
  (10:40 PDT) and force-stopped at xo 70C (402 of 1390s, 5.83 W, over the
  cold-start power guidance) -- a no-result void, not a FAIL, per hostops's
  10:58 PDT addendum (confirmed directly against `.hostops-diagnosed`).
  **Not re-queuing it**: it already has a separate, live Thor Playable
  confirmation from before this pass (`1-1790515369-lanelocal-1183547`),
  so it's already Playable and already counted -- a fresh confirmation
  would be redundant device time.
- `-3086875` (187: Ride or Die) and `-3086903` (Arctic Thunder) are still
  queued on the Nova, unaffected.
- Session 10's Thor cold-start confirmation (Otogi: Myth of Demons,
  `-43486`, `--hard-pin`, defaults) is still running.
- The Thor is now under a fresh hold (`lanelocal-fanwait`, placed
  2026-09-30 ~10:48 PDT, light work only, no new queued runs) until
  lane.local's fan repair lands -- not queuing anything further on the
  Thor until it lifts.
- Ibcache's three queued Crimson Nova runs, DOA's fight-route authoring,
  lane.kabukistall's stall explanation, #583 (Forza) and #591 (GTA SA) are
  all still open per the existing tier B/C ranking -- confirmed #591 still
  not folded into `origin/master` this session, unchanged.
- AUF needs its own authored route before it can be re-measured; not this
  lane's scope to author it.
