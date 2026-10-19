# fpsnext1019: GTA III CPU-side levers (HAKUX_FBLOOP, vtxstale1018/C2) all confirm but don't reach the player; Blinx 2/Fable captures (#433)

State: ready

Lane: fpsnext1019            Issue: #433
Base: master @ 656bcd1fe9
Files: docs/lanes/fpsnext1019/NOTES.md, docs/lanes/fpsnext1019/PR.md, docs/lanes/fpsnext1019/FINDINGS.md,
  docs/lanes/vtxstale1018/NOTES.md, docs/lanes/vtxstale1018/PR.md, docs/lanes/vtxstale1018/FINDINGS.md,
  docs/testing/jobs/selftest.d/99-vtxstale-pages.sh, hw/xbox/nv2a/pgraph/vk/draw.c,
  hw/xbox/nv2a/pgraph/vk/texture.c, hw/xbox/nv2a/pgraph/vk/buffer.c, hw/xbox/nv2a/pgraph/vk/renderer.h,
  hw/xbox/nv2a/pgraph/vk/vertex.c, hw/xbox/nv2a/pgraph/vk/vtxstale.h (new)
Prediction: none: no golden covers a GTA III driving-scene fps claim, so ab_compare.py cannot register it. Two
  falsifiable G3 predictions are in NOTES.md: "G3 prediction for HAKUX_FBLOOP" (committed 6e15857f0e, before any
  device run) and "G3 prediction: C2 on GTA III's driving save-state scene" (committed before the vtx1 batch).
Needs device: yes    Needs NDK: yes

On GTA III's in-car scene, one 128x128 colour target is sampled 40-140 times a flip while it is the target being
drawn. Each sample ends the render pass so that a barrier can make the pass's writes visible to the sample. The
pass count tracks frame time (ms/flip = 30.89 + 0.1309 x passes/flip), and these samples are up to 140 of the ~150
passes a flip.

`HAKUX_FBLOOP=1` (opt-in, default off) records that barrier inside the open pass instead. Turnip, which PurpleVK
is, takes an in-pass barrier with a stage outside framebuffer space as a full one. It renders that pass in sysmem,
flushes the colour cache, invalidates the texture cache and waits for idle, which is the same sync the break gave,
without the pass end and begin. The construct is outside what the Vulkan spec allows in a pass, so the switch
checks the driver and stays off on anything but Turnip. `HAKUX_FBLOOP=2` alternates off and on per 60-flip window
for same-scene comparison. Perflog builds report `fbs=`, `fbl=` and `fbon=` on each `[dipwin]` line.

Device results: batch `g3` scored against P0-P4 (NOTES.md "Attempt 8"). Mechanism (P0), passes (P1), pixels (P3)
and stability (P4) all confirmed/pass clean -- but P2 (time/fps) is falsified in the wrong direction: drive fps
F-arm mean 19.95 vs S-arm mean 23.05 (predicted +3.0, measured -3.1), M1's own on/off palindrome mean ms/flip
delta -2.29 ms (predicted a gain). **Does not ship** (stays opt-in, default off): a regression across all 5 arms
shows ms/flip tracks total draws/flip better than render-pass count, and FBLOOP's barrier costs a fixed
+1.3-1.6 ms/flip of its own (the sysmem-forcing drain) on top of whatever draw volume already costs -- removing
the pass break bought nothing because the drain it replaced was no cheaper. See FINDINGS.md for the summary row.

A second, independent CPU-side lever hits the same wall. lane/vtxstale1018 (#1049, merged this branch in
61deafb89e) replaces the per-frame-rotation vertex-RAM copy's one lowest-to-highest byte span (tens of MB around
a few hundred KB of real writes) with a per-4KB-page stale bitmap (`vtxstale_mark`/`vtxstale_copy`,
`hw/xbox/nv2a/pgraph/vk/vtxstale.h`), copying only the pages actually written. It had only ever been measured on
selftest and an on-foot capture; this branch built it (perflog) and ran it on GTA III's driving save-state scene
for the first time (batch `vtx1`, NOTES.md "Attempt 8, continued: C2"). The raw `score2.txt` drive window looked
like a regression (C1/C2 18.9/18.1 fps vs S1/S2 21.7/24.4), but video review (ffmpeg frame sampling) showed that
window is contaminated by a crash for the new arms too -- the lane's known `score2.py` fixed-window hazard
(FINDINGS.md). Re-scored on a matched, crash-free `[RT+1,RT+12]` window across all four arms: C2 20.9->17.4 fps,
53.0->60.4 ms/flip (S1 20.9/47.8, S2 16.8/62.7, C1 20.9/53.0). P1 (mechanism) confirms cleanly and quantitatively:
`dwcost.py`'s `stale` field drops from 3.60-3.88 ms/flip (S1/S2) to 0.05 ms/flip (C1/C2), matching the code
audit's estimate. P2 (time/fps) is falsified: total ms/flip does not fall, because `rotfen`/`fin_stalled`
(GPU-bound rotation-fence wait) rise +5.2 to +7.3 ms/flip, more than the stale-copy saving -- the freed CPU time
is absorbed by the GPU-bound wait rather than reaching the player. P3 (pixels) and P4 (stability) pass. **Does
not ship as a driving-scene fps win** (C2 is otherwise correct and already on master via the vtxstale1018 merge;
this is a measurement result, not a revert).

This is the third CPU-side fix this lane has measured against GTA III's driving scene that hits the identical
failure mode: HAKUX_FBLOOP's barrier, SWZKEEP's eviction-skip (Blinx 2), and now C2's stale-copy all save CPU
time that the GPU-bound rotation-fence wait re-spends instead of releasing to the player. FINDINGS.md's GTA III
rows and NOTES.md name this pattern explicitly. Next-ranked step: profile what the GPU is doing during
`rotfen`/`fin_stalled` on this scene, ahead of Addendum 4's remaining C1/C3/C4/C6 (C1 is another CPU-side
fence/lock item and would likely hit the same wall unmeasured).

Release note (none): opt-in HAKUX_FBLOOP switch for GTA III's feedback sample, off by default; vtxstale1018's C2
is a correctness-equivalent internal optimization, also off the player-visible path either way.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
