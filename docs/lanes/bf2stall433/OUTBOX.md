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

## #433 -- 2026-10-02 07:45 PDT

[lane.bf2stall433] Battlefield 2's per-draw GPU cost: the vertex-fetch fix is refuted, and the draws turn out to be serialized. No emulator change ships from this lane; the next fix is named, and so is the counter that sizes it.

- **Vertex fetch: refuted on the device.** The premise held: BF2's vertex
  data is read from IO-coherent cached memory (`host type 1 flags 0xf
  cached=1 coherent=1`). Moving it to a device-local mirror changed
  heavy-view GPU time from 35.9 to 36.0 ms (needed <= 0.80x). The fix is
  reverted, and its 4 queued pixel arms were withdrawn to
  `queue/withdrawn/`. Its GTA check is withdrawn with it.
- **The draws are serialized.** With Turnip's `syncdraw` (a full GPU drain
  before every draw), heavy-view GPU time rose only 35.15 -> 43.9 ms (+3.8 us
  per draw). If the draws normally overlapped, a drain per draw would cost far
  more. So BF2's ~2,150 draws a frame already run close to one at a time: the
  12-14 us per draw is exposed latency, which is why a faster GPU clock did
  not help.
- **Prime suspect:** every draw rebinds the uniform block at a new offset. In
  Turnip that is a new descriptor set, an invalidation of every bindless
  cache, and a constant reload before the draw can run.
- **The fix that fits the Adreno:** pass the constants a game changes between
  draws as push constants (loaded straight from the command stream, no
  descriptor change), and rebind the UBO only when its content changes. It
  lives in vk/shaders.c, glsl/vsh*.c and draw.c, outside this lane's
  territory, so it needs a new lane.
- **First step for that lane:** a perflog histogram of how many constant
  registers BF2 writes between draws. If most draws change <= 8-16 vec4, the
  fix removes the rebind from most draws.
- Runs used: 3 of 6 (A1, B1, syncdraw). Detail:
  `docs/lanes/bf2stall433/NOTES.md` sections 6-8, `PR.md`.
