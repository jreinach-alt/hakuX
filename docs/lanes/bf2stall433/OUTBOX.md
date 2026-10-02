# lane.bf2stall433 outbox

## #433 -- 2026-10-02 06:45 PDT

[lane.bf2stall433] Battlefield 2's per-draw GPU cost: reading done, fix built, arm registered.

- **The per-draw path (no device).** In BF2's heavy views (~2,150 draws, 45
  render passes a frame) there is **no per-draw barrier, event wait or
  render-pass split** on master: ~7 barriers a frame, and 41.8 of 42.6 ms of
  GPU time is inside render passes.
- **What every draw does pay:** its vertex fetch reads guest vertex RAM from
  host copies that VMA places in cached memory. On Turnip/KGSL, cached memory
  on ARM is IO-coherent, so the GPU snoops the CPU caches on every fetch. That
  latency does not scale with the GPU clock, which is what collapse433
  measured. Every draw also pays a full constant reload; fixing that is
  outside this lane's files.
- **Fix (vk/draw.c only):** a device-local mirror of vertex RAM. It is updated
  in the existing aux command buffer with only what was uploaded, and draws
  bind it. Same bytes, so pixels should not move. `HAKUX_VTX_MIRROR=0` turns
  it off.
- **Registered before any run:** BF2 3+3 Nova soaks (master vs head, default
  regimen, binned by draws). Pass = heavy-view GPU ms down 20% or more. A full
  golden sweep plus the Stencil/VSH-rounding flip band, every capture
  identical, is queued by the arms job.
- **Budget:** the BF2 pair takes all 6 of my Nova runs. The second-title
  check (GTA, `bf2stall433-gta-soak.json`) is registered but needs 6 more
  Nova runs from lane.local.
