# fpsnext1019: GTA III in-pass feedback barrier (HAKUX_FBLOOP, opt-in), Blinx 2 and Fable gameplay captures (#433)

State: ready

Lane: fpsnext1019            Issue: #433
Base: master @ 656bcd1fe9
Files: docs/lanes/fpsnext1019/NOTES.md, docs/lanes/fpsnext1019/PR.md, docs/lanes/fpsnext1019/FINDINGS.md, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/texture.c
Prediction: none: no golden covers a GTA III driving-scene fps claim, so ab_compare.py cannot register it. The
  falsifiable G3 prediction (P0-P4) is in NOTES.md, "G3 prediction for HAKUX_FBLOOP", committed in 6e15857f0e
  before any device run.
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

Release note (none): opt-in HAKUX_FBLOOP switch for GTA III's feedback sample, off by default.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
