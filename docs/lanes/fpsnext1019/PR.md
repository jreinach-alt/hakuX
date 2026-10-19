# fpsnext1019: GTA III driving, Blinx 2 and Fable toward 30 fps (#433)

State: ready

Lane: fpsnext1019            Issue: #433
Base: master @ d30f91349b (fpsdata1018, foldjam1018, compat1019b and nova-tiers1019's folds landed on master, plus this lane's own attempt-4 fold; merged in)
Files: docs/lanes/fpsnext1019/NOTES.md, docs/lanes/fpsnext1019/PR.md, docs/lanes/fpsnext1019/FINDINGS.md, hw/xbox/nv2a/pgraph/vk/texture.c, hw/xbox/nv2a/pgraph/vk/surface.c
Prediction: none: ab_compare.py's golden-capture registration does not fit a GTA III driving-scene fps claim (no
  golden exists for it). The falsifiable prediction that mattered (NOTES.md, "one guard dominates wrej[], likely
  scale/shape, not off") was written before the device run that tested it and was falsified by that run -- see
  NOTES.md "Attempt 2, item 3". The fix that followed was measured on-device (pre-authorised GTA III save-state
  protocol, this lane's own Nova hold) before landing, not registered through ab_compare
Needs device: yes    Needs NDK: yes

GTA III: recovered and analyzed attempt 1's SYSMEM/GMEM render-mode hold batches (contested, not a clean win either
direction -- see FINDINGS.md), then found every captured arm's surface-to-texture copies are 100% caused by a
texture component-map mismatch (`S2C_MAP`). Added reject-reason counters to `s2t_widen_view()` to find out which of
its guards was rejecting the fast path built for exactly this case (R2, lane gta3fps1017b) -- and found none of
them were: R2 is gated behind an opt-in env var (`HAKUX_S2T_WIDEN`) that had never been set in any capture taken by
this lane or its predecessor. Turned it on and measured it (one run: hold 25.3->28.3 fps, drive 23.7->27.1 fps,
render-passes/flip 47->33, the S2C_MAP copy eliminated entirely for the whole run), pixel-sanity-checked
(same-save-state frame diff 1.4, threshold 3.0, MATCH), then **landed the default flip** (commit `3058a55767`,
`"0"` still opts out, same pattern as `HAKUX_S2T_FB` mode 2). Two further confirming runs on the new default
reproduced the render-pass drop in both but showed noisier fps, one confounded by a fresh-install shader-cache
clear -- reported honestly in NOTES.md rather than re-run past this attempt's device-time budget. Then resolved the
SYSMEM/GMEM contest at zero new device time: `score2.py`'s "drive" window turned out to be an unverified fixed
span, and the shipped-baseline arm (S1) actually crashes into a wall inside it (~RT+25); re-scoring all three
attempt-1 arms on a crash-excluded, motion-verified, equal-length window (`movescore.py` + `dwseries.py`) shows
sysmem clearly beats shipped (24.2 vs 21.3 fps, fewer render passes and S2C copies/flip) and gmem does not -- not
yet landed (it is a Turnip env var, needs a per-title default mechanism, not a code change here). Tested whether
sysmem and the now-default-on `HAKUX_S2T_WIDEN` stack: one clean, crash-checked run on the same window shows they
do **not** -- render passes/flip rose to 148.4 (worse than shipped's 130.2) and fps fell to ~20 (worse than every
other arm measured), even though R2's own copy-elimination still engaged (`cs2t-ended/flip` 0). Conclusion: if
sysmem is ever shipped as a per-title default, it should not be paired with R2's default-on without a further,
separate test. Blinx 2:
root-caused why the generic dispatcher drive route never reaches gameplay (`EXPLORE_LADDER` excludes `START`
without a built profile), then bypassed it: the owner's island save state is already on the Nova debug package
(slot 5) and loads through the same pause-menu protocol GTA III uses, so Blinx 2 gameplay needed no profile work
at all. Beyond R2, GTA III's in-car scene still ends up to 140 of ~150 render passes/flip on a sample of one
128x128 colour target; built two opt-in, falsifiable-predicted (G3) levers to test the two candidate mechanisms:
`HAKUX_S2T_DEAD` (GTA III -- keep the node's image when no combiner reads the sampled texel) and `HAKUX_SWZKEEP`
(Blinx 2 -- keep a swizzle-only re-marked binding bound instead of evicting+re-shelving it, the cause of a 256x256
depth surface being evicted and downloaded twice a flip). Both ran their full device palindromes this attempt.
`HAKUX_S2T_DEAD`'s own mechanism-deciding prediction (P0) is **falsified**: zero dead texels in 631,040
feedback-sample events across three full runs -- the sampled texel is real feedback on this scene, not a fetch
nothing reads, so the lever cannot engage (and measurably doesn't: on-vs-off pixel diff 0.1). The remedy for GTA
III's remaining passes is a feedback-loop attachment or in-pass self-dependency, not this lever. `HAKUX_SWZKEEP`'s
mechanism prediction (P1) **holds cleanly** (the targeted eviction/download/fence-wait pattern drops to zero on
arms, confirmed four independent ways), but its fps (P2, +1.0 measured vs +3.2 predicted -- the saved CPU wait
reappears as more GPU render time or a different idle stall) and pixel (P3, a visible elongated double-shadow
artifact on both on arms, ~2.5x the off-vs-off noise floor) predictions do not -- **`HAKUX_SWZKEEP` does not
ship.** Both switches are opt-in/default-off, so neither needs further gating; both results are real, instrument-
and pixel-backed negatives, not "needs more data." Fable:
H2's zeta/colour eviction-download pattern (`[edl]`, landed by fpsdata1018, never run before this attempt)
reproduces reliably from a cold boot -- no route or save state needed (all 4 of Fable's existing states are
schema-incompatible on the current build) -- once a perflog APK is actually installed (the first attempt read
zero census lines against a plain debug build; `opt_stats_log_and_reset()` compiles to nothing without
`-Pperflog=true`, a build-selection miss, not a scene finding). A 27-window/~95s capture reads `clrskip`/`dl` =
**0.504**, not the 1.0 ("6/6") Addendum 2 set as the bar for building an unconditional download-skip lever --
close to half of every window's evicted-and-downloaded content is real feedback a later stage reads, so the
lever is **not built**. A conditional, per-binding skip is the next-ranked option if this is picked back up, not
started this attempt. RalliSport 2: read back fpsdata1018's landed `HAKUX_TEXSCAN2D` default against real
gameplay for the first time (previously only pixel-sanity-proven) -- on the kept dispatcher route, the ON arm
shows zero `sdown` (deferred-download fence-wait) in every driving-phase window and a 59.0fps mean, the OFF arm
(`HAKUX_TEXSCAN2D=0`) shows `sdown` in 63/63 driving windows and a 38.2fps mean, same route, only the env var
differs -- confirmed on real data, nothing further to do on this lever. (Both arms still show `sdown` on
pre-race menu/flyover screens; the claim is scoped to the driving phase, which is what the bar measures.) Fable's
half of this read-back (`HAKUX_S2T_FB` mode 2 against `tobuf`) is not yet done. Detail in
`docs/lanes/fpsnext1019/NOTES.md`; per-title table in `FINDINGS.md`.

Release note (performance): GTA III driving scenes do fewer GPU render passes per frame (a texture copy the
renderer was already built to avoid, but had never been turned on, now runs by default); measured as an fps
increase on one of three device trials, flat on the other two once a one-time shader-recompile cost on the first
trial is accounted for. The two opt-in diagnostic switches added this attempt (`HAKUX_S2T_DEAD`, `HAKUX_SWZKEEP`)
default off and are not shipped behaviour changes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
