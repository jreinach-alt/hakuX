# lane.verdict433: measurement pass for #433 (0.5: 50 Playable)

State: draft

Lane: verdict433            Issue: #433 [#507]
Base: master @ 94cf8eb627 (branched); merged forward to 2dd92568b5 as of session 7
Files: docs/lanes/verdict433/NOTES.md, docs/lanes/verdict433/PR.md, docs/lanes/verdict433/OUTBOX.md, docs/lanes/verdict433/judge_copy.py, docs/lanes/verdict433/scan.py, docs/lanes/verdict433/soaks.py, docs/lanes/verdict433/sweep.py, docs/lanes/verdict433/queue_batch1.sh, docs/lanes/verdict433/queue_batch2.sh, docs/lanes/verdict433/queue_batch3.sh, docs/lanes/verdict433/queue_batch4.sh, docs/lanes/verdict433/queue_batch5.sh
Prediction: none: analysis-only (no emulator code changed; this lane only reads device results and queues confirmation soaks through the normal harness)
Needs device: yes (Nova; Thor confirmations withdrawn per lane.local's 2026-09-29 12:00 PDT addendum -- heat-sensitive work moved off the Thor pending #507)

## Summary

This lane's brief (#433, 2026-09-29 06:3x PDT): turn titles that already run
well into Playable verdicts, using the harness's normal confirmation
pipeline, and re-measure titles that this week's fixes moved. No emulator
code, Playable rule, or board file is touched -- this is a measurement-only
lane that reads `title_verdict.py` output and queues confirmation soaks via
`docs/testing/request.sh`.

Across seven sessions (2026-09-29 through 2026-09-30, each one queuing a
batch and stopping to let 20-30 min device soaks run rather than polling):

- **Two titles confirmed Playable this pass, both on the Nova at the
  default confirmation regimen:**
  - **KOF: Maximum Impact - Maniax** -- fps_ok=0.9936, gameplay 1282.6s, no
    crash/hang, audio_short=0.0005, 0.1121 J/frame.
  - **Azurik: Rise of Perathia** -- fps_ok=0.9521, gameplay 1292.3s, no
    crash/hang, audio_short=0.0, 0.228 J/frame. (This title FAILED its Thor
    confirmation on heat in session 2 -- `thermal-pause-F8` at +938s from a
    cool 48.6C start; moving it to the Nova per lane.local's addendum is
    what turned it Playable.)
- **007: Agent Under Fire** read `100%` at the bar on Nova route soaks after
  PR #530 (per-title sysmem) folded, but its confirmation attempt hit a
  harness bug: the shared `titles.qcow2` HDD file was pushed to the Nova
  with `adb push`'s default `rw-r--r--` permissions, one group-write bit
  short of what xemu needs to open it (root-caused by hostops mid-session,
  same bug as PR #627/lane.hddperm, #397). Two sibling runs in the same
  batch (WWE Raw 2, 50 Cent) voided outright on this; AUF's run started
  just before the interim chmod fix landed and instead hung silently at
  `qemu_init` for the full 1475s timeout. Rerun queued (`-366094`).
- **Baldur's Gate: Dark Alliance** booted clean (after the chmod fix),
  played its full route into gameplay, and ran 1684 of 1760 planned
  seconds (1190s of gameplay, 10s short of the 1200s bar) before an adb
  capture flake (`adb failed (exit 1)`, 5 consecutive polls) aborted the
  soak. No crash, no hang, no low-fps reading -- a single-run device flake
  this close to the bar gets a rerun before any conclusion. Rerun queued
  (`-366130`).
- **WWE Raw 2 and 50 Cent: Bulletproof** voided on the same `titles.qcow2`
  permission bug as AUF. hostops already re-queued both
  (`-1456493r2`, `-1456544r2`); this lane did not queue a third attempt.
- Full ranking, tier A/B/C readings, and the session-by-session log (7
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

- `-366094` (AUF rerun) and `-366130` (BG:DA rerun) have not finished.
- The hostops-owned `-1456493r2` (WWE Raw 2) and `-1456544r2` (50 Cent)
  requeues have not finished.
- Ibcache's three queued Crimson Nova runs, DOA's fight-route authoring,
  lane.kabukistall's stall explanation, #583 (Forza) and #591 (GTA SA) are
  all still open per the existing tier B/C ranking -- unchanged this
  session.
