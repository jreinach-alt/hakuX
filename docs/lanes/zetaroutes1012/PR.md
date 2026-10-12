# zetaroutes1012: returning gameplay routes for Buffy, DOA3 and NG Black, then HAKUX_ZETA_D24=1 runs (#433, 0.5)

State: in-progress

Lane: zetaroutes1012          Issue: none (lane.local dispatched directly; #433 umbrella)
Base: master @ 78cd417e9d
Files: docs/lanes/zetaroutes1012/NOTES.md, docs/lanes/zetaroutes1012/PR.md, docs/lanes/zetaroutes1012/OUTBOX.md,
docs/testing/titles/routes/buffy.returning.route, docs/testing/titles/routes/doa3.returning.route,
docs/testing/titles/routes/ninja-gaiden-black.returning.route
Prediction: none yet (queued after a switch-on run reaches the bar; see step 6 of the brief)
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

Buffy's first switch-on sweep run (`z-1791817586-lane.zetaroutes1012-2316443`) reached the mark cleanly
(fps_ok=1.0, gameplay=777.6s, no crash/hang) but FAILed `title_verdict.py` on a static-window check: the
route's play loop (reused verbatim from `buffy.route`, itself an unconfirmed DRAFT) ran Buffy face-first
into the canyon's wall within ~20s of the mark and left her pinned there for the rest of the run -- a route
defect, not a `HAKUX_ZETA_D24` finding. NOTES.md section 6 has the frame-by-frame evidence. The play loop is
fixed (section 7): short forward pulses with turns between them, the pattern `spikeout.returning.route`'s
confirmed-working loop uses, instead of holding forward for 7+ seconds unsteered. A pilot verdict is written
(`dispatch/pilots/lane.zetaroutes1012.ok`), and three runs are now queued: the fixed Buffy route, plus DOA3
and NG Black's switch-on sweep runs (`z-1791820250-lane.zetaroutes1012-2510625`,
`z-1791820275-lane.zetaroutes1012-2514338`, `z-1791820279-lane.zetaroutes1012-2514939`; NOTES.md section 8).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
