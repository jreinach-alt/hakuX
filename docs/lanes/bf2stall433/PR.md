# bf2stall433: draws fetch vertex RAM from a device-local mirror (#433)

State: draft

Lane: bf2stall433            Issue: #433
Base: master @ b71f92a12a
Files: hw/xbox/nv2a/pgraph/vk/draw.c, docs/lanes/bf2stall433/PR.md, docs/lanes/bf2stall433/NOTES.md, docs/lanes/bf2stall433/OUTBOX.md, docs/lanes/bf2stall433/armread.py, docs/lanes/bf2stall433/register_pixels.py, docs/testing/predictions/bf2stall433-bf2-soak.json, docs/testing/predictions/bf2stall433-gta-soak.json, docs/testing/predictions/bf2stall433-pixels.json, docs/testing/predictions/bf2stall433-band.json
Prediction: docs/testing/predictions/bf2stall433-bf2-soak.json (+ -pixels, -band, -gta-soak)
Needs device: yes    Needs NDK: yes

## What the per-draw path does (steps 1-2, no device)

Battlefield 2's heavy views run ~2,150 draws a frame in 45 render passes,
with ~7 barriers a frame. **No barrier, event wait or render-pass split happens
per draw on master.** The GPU's time is inside the render passes (41.8 of 42.6
ms). What every draw does pay:
- **V:** every vertex fetch reads the per-frame host copies of vertex RAM.
  They are allocated HOST_ACCESS_RANDOM, so VMA prefers HOST_CACHED memory. On
  Turnip/KGSL the only cached type on ARM is IO-coherent, so each vertex fetch
  snoops the CPU caches. That cost does not shrink with the GPU clock, which
  matches collapse433's measurement.
- **U:** a fresh uniform block, descriptor rebind and constant reload on every
  draw. The fix for U is in vk/shaders.c and the GLSL generators, outside this
  lane's territory.

Full table and sources: `docs/lanes/bf2stall433/NOTES.md` sections 1-3.

## The fix (step 3)

One device-local copy of vertex RAM. Only what was uploaded since the last
finish is copied into it, in the aux command buffer that already copies the
index and uniform data, and draws bind it. Same bytes at the same moment, so
pixels should not move. `HAKUX_VTX_MIRROR=0` turns it off. `[vtxmirror]` logs
the memory types (the premise) and the bytes copied (the cost). NOTES section
4.

## Prediction and device runs

Registered before any run; see NOTES section 5. Results: pending.

Release note (performance): fewer GPU stalls in draw-heavy scenes (Battlefield 2 heavy views), if the arm confirms it.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
