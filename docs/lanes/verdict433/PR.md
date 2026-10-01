# lane.verdict433: measurement pass for #433 (0.5: 50 Playable)

State: draft

Lane: verdict433            Issue: #433 [#507]
Base: master @ 94cf8eb627 (branched); merged forward to origin/master @ b1cea467c6 (the #583 and #569 P3 folds) in session 17
Files: docs/lanes/verdict433/NOTES.md, docs/lanes/verdict433/PR.md, docs/lanes/verdict433/OUTBOX.md, docs/lanes/verdict433/judge_copy.py, docs/lanes/verdict433/scan.py, docs/lanes/verdict433/soaks.py, docs/lanes/verdict433/sweep.py, docs/lanes/verdict433/queue_batch1.sh, docs/lanes/verdict433/queue_batch2.sh, docs/lanes/verdict433/queue_batch3.sh, docs/lanes/verdict433/queue_batch4.sh, docs/lanes/verdict433/queue_batch5.sh, docs/lanes/verdict433/queue_batch6.sh, docs/lanes/verdict433/queue_batch7.sh, docs/lanes/verdict433/queue_batch8.sh, docs/lanes/verdict433/queue_batch9.sh, docs/lanes/verdict433/queue_batch10.sh
Prediction: none: analysis-only (no emulator code changed; this lane only reads device results and queues confirmation soaks through the normal harness)
Needs device: yes (Nova for all confirmations; Thor cold-start-only per the 2026-09-30 10:20 PDT addendum, capped at 3/day, light titles under ~4.5W net)

## Summary

This lane's brief (#433, 2026-09-29 06:3x PDT): turn titles that already run
well into Playable verdicts, using the harness's normal confirmation
pipeline, and re-measure titles that this week's fixes moved. No emulator
code, Playable rule, or board file is touched -- this is a measurement-only
lane that reads `title_verdict.py` output and queues confirmation soaks via
`docs/testing/request.sh`.

Across seventeen sessions (2026-09-29 and 2026-09-30, each one queuing a
batch and stopping to let device soaks run rather than polling):

- **Six titles confirmed Playable this pass, all on the Nova at the
  default confirmation regimen; seven Playable in total with Alien
  Hominid (09-26).** Each pass's mark frame was reviewed under the
  09-30 20:10 PDT rule (NOTES, session 17, names each frame):
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
  - **Crimson Skies: High Road to Revenge** (session 15) -- fps_ok=0.95,
    gameplay 708.9s, no crash/hang, audio_short=0.0, 0.2145 J/frame. The
    first 600-s-native confirmation this lane has judged under the 09-30
    12:10 PDT rule change (audit counter: 1 of 5, not yet due for a
    1200-s re-run). Its first queue attempt was withdrawn by a
    false-positive "Galleon" match before this pass; see below.
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
- **187: Ride or Die is withdrawn: its route ends on profile creation.**
  It read fps_ok=1.0 over 1286.4s, but the owner's frame review showed the
  scored window is the profile-creation screen, not a race. A menu at 60
  fps scores 100%. Not counted.
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
- **Arctic Thunder is not Playable**: a full-length (684s) run reads only
  63.9% at 28.5+, contradicting four earlier short (195-198s) runs that all
  read 100% -- the route's own script runs out of steps at 684s rather than
  sustaining a full window, and what fps it does produce past that point
  falls well under the bar.
- **Otogi: Myth of Demons FAILs on heat** on the Thor
  (`thermal-pause-F8` at +703s, 35.0% at 28.5+, peak xo 77.9 C) -- recorded
  as heat evidence, not re-run there.
- **Alien Hominid** already carries a separate, earlier Thor Playable
  confirmation (`lanelocal-1183547`, 09-26) found during this pass; this
  lane's own Nova/Thor attempts at it were not needed and not re-queued.
- **A queued Crimson Skies confirmation was withdrawn as a false-positive
  "Galleon" match** (session 14): the withdrawn request's title field reads
  Crimson Skies, not Galleon, and Galleon's title ID appears nowhere in it
  -- the only trace of "Galleon" is flavour text in the route's own
  descriptive comment ("Galleon-era perf runs"), a prose match rather than
  a title match. Re-queued (`queue_batch9.sh`) and **PASSED Playable**
  (session 15, see above).
- **Re-checked 007: Agent Under Fire against two new long (1935-1941s)
  runs from an unrelated lane** (`lane.sustain507`, #507 Part C, session
  15) that happened to use the same generic route: same vault-door
  softlock this lane found in session 9 (frames pixel-identical 71 minutes
  apart). No change to its verdict.
- **Flagged for lane.titleroutes (session 15):** its new Shin Megami
  Tensei: NINE Thor screen looked like the day's best Thor cold-start
  candidate on paper (96.7% share, no crash/hang, 4.80W net) but its `mark
  gameplay` is an unvalidated `[guess]` placeholder that landed on the
  Japanese name-entry keyboard screen, not play -- the same failure mode
  DOA3's v1 route had. Not queued; needs the route fixed first.
- Full ranking, tier A/B/C readings, and the session-by-session log (15
  sessions, including a harness anomaly where an entire batch of six
  queued requests vanished from the dispatch tree without a withdrawal or
  error record, root-caused as unrecoverable and simply re-queued, and the
  false-positive Galleon withdrawal above) are in
  `docs/lanes/verdict433/NOTES.md`.

Release note (none): measurement/verification work only; no emulator code
changed.

## Local checks run (offline protocol -- no CI available)

- `python3 docs/testing/title_verdict.py <dir> --require confirmation
  [--reviewed-gameplay yes]` run directly against each finished result
  directory across all sessions; output captured in NOTES.md's tables.
- `git status` clean before and after each session's edits; only
  `docs/lanes/verdict433/*` files touched.
- No harness files (`docs/testing/*.py`, `docs/testing/jobs/*`) changed, so
  `docs/testing/jobs/selftest.sh` was not required per the offline
  protocol's fold checklist.

## Outstanding before ready

- **Batch 10 is queued on the Nova (session 17), on master b1cea467c6:**
  Kabuki Warriors (warm-up `1-1790826491-lane.verdict433-3477434`, then the
  1200-s confirmation `-3477568`, the second launch on the apk so P3's
  pre-build has recorded pipelines) and Forza Motorsport (1200-s
  confirmation `-3477700`, after the #583 decay fix). Both are flagged
  titles, so 1200 s. Judge each, review its frames after the mark, and
  record Kabuki's `shader_cache` state.
- Every earlier request has a final verdict (six PASS Playable, 187
  withdrawn, AUF and Arctic Thunder FAIL, Otogi FAIL on heat, Alien Hominid
  void/redundant).
- Merged `origin/master` twice (sessions 14 and 15), most recently 46
  commits, clean, no conflicts. Session 15's merge folded
  lane.uberspike569-gpl (#569's uber pre-raster library, but `HAKUX_GPL`
  still defaults to 0 -- no effect on this lane's default-regimen
  confirmations) and lane.titleroutes sessions 39-42 (Galleon
  owner-blocked in `targets.toml` too; six new Thor screening routes, none
  validated yet). #583 (Forza) folded since, in session 17's merge; #591
  (GTA SA/ibcache) has not.
- **Beyond batch 10, progress is gated on other lanes:** #591, and
  titleroutes revising its SMT: NINE and DOA3 routes from their own
  frames (both currently mark `gameplay`/`booted` on the wrong screen).
  Session 15's full sweep of every finished Nova and Thor route soak found
  no further confirmable candidate from current evidence -- re-sweep after
  any of the above lands.
- AUF needs its own authored route before it can be re-measured; not this
  lane's scope to author it.
- The `lanelocal-fanwait` hold referenced in earlier sessions is no longer
  present in `dispatch/hold/` as of session 15 (titleroutes queued and
  completed six Thor requests after it was placed) -- Thor is not
  currently held, but no good candidate was found to spend a slot on.
