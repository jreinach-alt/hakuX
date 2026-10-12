# zetaroutes1012: returning gameplay routes for Buffy, DOA3 and NG Black, then HAKUX_ZETA_D24=1 runs (#433, 0.5)

State: in-progress

Lane: zetaroutes1012          Issue: none (lane.local dispatched directly; #433 umbrella)
Base: master @ 78cd417e9d
Files: docs/lanes/zetaroutes1012/NOTES.md, docs/lanes/zetaroutes1012/PR.md, docs/lanes/zetaroutes1012/OUTBOX.md,
docs/testing/titles/routes/buffy.returning.route, docs/testing/titles/routes/doa3.returning.route,
docs/testing/titles/routes/ninja-gaiden-black.returning.route, docs/testing/predictions/zetaroutes1012-buffy.json
Prediction: docs/testing/predictions/zetaroutes1012-buffy.json (Buffy's switch-on run is at the bar; the off
leg is queued, --expect on this file)
Needs device: yes (the Nova, sweep tier)    Needs NDK: no

Building returning (kept-profile) gameplay routes for the three titles `HAKUX_ZETA_D24` lifted on the survey
route (fpsbelow1012, folded 78cd417e9d), so the switch can be confirmed on real moving gameplay instead of the
survey route's blind menu cycling. Boot tables for all three titles are in NOTES.md sections 1-3.

All three routes are composed and committed. `route.sh --check` passes on all three. `titlestate.admit()`
admits Buffy as `state: returning` (its kept profile has a save directory), but refuses that state for DOA3
and NG Black -- their kept-profile goldens are title data only, no save directory, which matches their own
boot tables (neither shows a load/continue/save-name screen). Per the gate's own suggested fix, both files'
header state is `# state: any` instead (filenames unchanged); NOTES.md section 4 has the detail. All three
now admit=True.

Buffy's first switch-on sweep run (`z-1791817586-lane.zetaroutes1012-2316443`) FAILed a static-window check:
the route's play loop (reused verbatim from `buffy.route`, itself an unconfirmed DRAFT) ran Buffy face-first
into the canyon's wall within ~20s of the mark and left her pinned there -- a route defect, not a
`HAKUX_ZETA_D24` finding (NOTES.md section 6). The loop was fixed (section 7: short forward pulses with turns
between them, `spikeout.returning.route`'s confirmed-working pattern), and the re-run
(`z-1791820250-lane.zetaroutes1012-2510625`) is a clean **PASS**: `fps_ok=1.0 gameplay=774.9s
static_frac=0.0394` (NOTES.md section 10). Its pair is registered (`zetaroutes1012-buffy.json`) and the
switch-off leg is queued (`z-1791823924-lane.zetaroutes1012-3538464`, NOTES.md section 13).

DOA3's switch-on run (`z-1791820275-lane.zetaroutes1012-2514338`) reached 781.2s of moving fight play
(`fps_ok=0.9773 static_frac=0.0`) but FAILed on a 632ms hitch: `logcat.txt`'s `[shd413]` perf line at the
stall shows `pc_ms=559.6` (pipeline-create time) for one new pipeline -- a first-use shader compile stall on
this route's combo-press pattern, not a `HAKUX_ZETA_D24` effect or a route defect (NOTES.md section 11).
Reported as a finding for the cross-title screen; no further run.

NG Black's switch-on run (`z-1791820279-lane.zetaroutes1012-2514939`) FAILed on duration alone (`gameplay=
589.7s` against the 600s bar, with `fps_ok=0.9956 static_frac=0.0216` -- no movement problem): its 11-repeat
genre loop finished at ~481s of scripted movement, and the ~314.5s of boot/menu/cutscene cadence above the
mark left too little of the 900s request after it. Fixed by raising the loop's outer repeat from 11 to 15
and the request's `--seconds` from 900 to 1020 (NOTES.md section 12); the re-run is queued
(`z-1791823930-lane.zetaroutes1012-3542868`).

Run count: 6 of the 12-run budget (4 read, 2 queued). Waiting on both queued runs' `DONE` files (NOTES.md
section 13).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
