# fpsnext1019: GTA III driving, Blinx 2 and Fable toward 30 fps (#433)

State: ready

Lane: fpsnext1019            Issue: #433
Base: master @ 2e6d29d4f8 (fpsdata1018's fold landed on master; merged in)
Files: docs/lanes/fpsnext1019/NOTES.md, docs/lanes/fpsnext1019/PR.md, docs/lanes/fpsnext1019/FINDINGS.md, hw/xbox/nv2a/pgraph/vk/texture.c
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
root-caused (not fixed) why the generic drive route never reaches gameplay -- the dispatcher's `EXPLORE_LADDER`
excludes `START` without a built profile, and Blinx 2 has none; deferred in favor of GTA III, which was directly
actionable. Detail in `docs/lanes/fpsnext1019/NOTES.md`; per-title table in `FINDINGS.md`.

Release note (performance): GTA III driving scenes do fewer GPU render passes per frame (a texture copy the
renderer was already built to avoid, but had never been turned on, now runs by default); measured as an fps
increase on one of three device trials, flat on the other two once a one-time shader-recompile cost on the first
trial is accounted for.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
