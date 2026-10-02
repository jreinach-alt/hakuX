# lane.bf2stall433 notes

#433 (0.5: 50 Playable). Brief: find the per-draw GPU stall behind Battlefield
2's heavy-view dips (collapse433 section 7: GPU time is ~12-14 us per draw and
does not shrink at 1.53x the GPU clock or in sysmem) and fix it.

Base: master b71f92a12a. Counter reads are from COPIES of collapse433's three
perflog soaks (`.scratch/soak/`, not committed): GMEM `-390126`, sysmem
`-601955`, max `-967641`. Driver source is Mesa Turnip at the sha
`turnipcost569` builds (`4c18636110`), the closest public tree to the fleet's
PurpleVK `git-62ac221a33` (`.scratch/tu/`, extracted with `git show`, not
committed).

## 1. What the renderer emits per draw (step 1)

A heavy window of the GMEM soak (22:48:2x, 60 flips): `BE:2154 DA:57 IE:2097`,
`PBnd:808 SBnd:2148 RP:45`, `GBU:21/2143/0/0/0`, `rpbrk RP:2689(fin15 qry52
clr120 nd295 srf2207) Bar:446`, GPU `R:41.8 X:0.8 g:44/1/0`.

| item | where (vk/draw.c) | per draw? | heavy view, per frame |
|---|---|---|---|
| pipeline barrier | `sync_staging_buffer`, `flush_memory_buffer`, `begin_render_pass` zeta transition, finish WAR/aux | **no**: aux CB at finish, or render-pass start | `Bar` 446 / 60 = ~7 |
| render-pass break | `begin_draw` (query, clear), surface changes | **no** | `RP` 45 for 2,154 draws (~48 draws per pass); breaks are `srf` (surface) and `qry` |
| event / wait inside a pass | none found | -- | 0 |
| `vkCmdUpdateBuffer` / copy inside a pass | none; index, inline-vertex and uniform data go to staging and are copied by the aux CB at finish | **no** | `Xfr` 0.8 ms |
| `vkCmdBindPipeline` (+ zero vertex buffer, viewport, scissor, every dynamic state re-issued) | `begin_draw` | on change | `PBnd` 808 |
| dynamic state | `begin_draw` (cull, front face, blend constants, depth, stencil, EDS3 blend) | on register change only | -- |
| UBO descriptor set, **new dynamic offsets** | `bind_descriptor_sets` | **yes, every draw** | ~2,150 |
| texture push descriptors | `bind_descriptor_sets` | when texture bindings change | -- |
| push constants (attr values, line params) | `push_vertex_attr_values`, `push_geom_line_params` | yes | ~2,150 x 2 |
| uniform upload (whole VS+PS layout to the staging ring) | `pgraph_vk_update_shader_uniforms` -> `pgraph_vk_update_descriptor_sets` | **yes** when constants are dirty (`SBnd` = BE) | ~2,150 |
| vertex buffers bind (`BUFFER_VERTEX_RAM`) | `bind_vertex_buffer` | yes | ~2,150 |
| index data (inline elements, 97% of BF2 draws) | `pgraph_vk_update_index_buffer` -> staging -> aux copy | yes | `GBU` idx 2,143 |

**There is no per-draw barrier, event wait or render-pass split on master.** The
GPU timestamps agree: `R` (time inside render passes) is 41.8 of 42.6 ms, and
44 of 45 inter-pass gaps are under 0.1 ms. So the 12-14 us per draw is spent
INSIDE render passes, draw after draw.

What the draws do pay, every one: a fresh UBO region and a descriptor rebind
with new dynamic offsets. In Turnip that copies the dynamic descriptors into a
new reserved set and re-emits the bindless bases with `SP_UPDATE_CNTL
gfx_bindless=0xff` (`tu_bind_descriptor_sets`, `tu6_emit_descriptor_sets`), and
the A740 loads the pushed UBO ranges into the constant file in each shader's
preamble. And a vertex fetch from `BUFFER_VERTEX_RAM` (section 2).

## 2. Where vertex data comes from (step 2)

- Vertex attributes from guest RAM are read by the GPU straight out of the
  per-frame `FRAMEn_VERTEX_RAM` buffers (64 MB each), bound by
  `bind_vertex_buffer` and the reorder path's `snapshot_vertex_buffers`.
- Those buffers are created in `vk/buffer.c` with
  `VMA_MEMORY_USAGE_AUTO_PREFER_HOST` + `VMA_ALLOCATION_CREATE_HOST_ACCESS_RANDOM_BIT`.
  VMA turns HOST_ACCESS_RANDOM into a REQUIRED `HOST_VISIBLE | HOST_CACHED`.
- Turnip on KGSL (`tu_knl_kgsl.cc` ~303; `tu_device.cc` ~1774) exposes no
  cached NON-coherent type on ARM (`has_cached_non_coherent_memory = ... &&
  !DETECT_ARCH_ARM`), so the only HOST_CACHED type it can offer is the
  cached-coherent one, allocated with `KGSL_MEMFLAGS_IOCOHERENT |
  KGSL_CACHEMODE_WRITEBACK`, present when the kernel reports IO-coherence.
- **Correction (same session):** this VMA version only PREFERS
  HOST_CACHED for HOST_ACCESS_RANDOM (`vk_mem_alloc.h` ~4066: "Cannot require
  it"). So the allocation succeeding does not prove a cached type exists. The
  fix logs the memory type the host copies actually got (`[vtxmirror] on: ...
  host type N flags 0x.. cached=? coherent=?`). The prediction's P0 reads that
  line first: with `cached=0` there is no snoop to remove, and the arm is
  INERT by premise, not a refutation.
- **So every vertex fetch in every draw is an IO-coherent read: the GPU's
  request snoops the CPU caches through the interconnect.** That path's latency
  is set by the memory system and the CPU cluster's coherency fabric, not the
  GPU core clock: the shape collapse433 measured (slope 11.9 us per draw at
  401 MHz, 14.2 at 615 MHz).
- The data is nearly static. `[rdc] vtx=` reads ~1,050 dirty-bitmap walks per
  60 flips with 0-12 dirty hits, and `GBU` shows ~20 vertex-RAM uploads a frame
  against ~2,150 draws. The same bytes are fetched through the snoop path
  frame after frame.
- Index data is not on this path: inline-element indices are staged and
  copied into `BUFFER_INDEX`, which is device-local.

## 3. The cause the code supports, and the competing one

Two per-draw costs are bound by memory latency, which fits a slope that does
not shrink with the GPU clock:

- **V (vertex fetch through IO-coherent memory).** Above. Fix in reach: keep
  a device-local mirror of vertex RAM, copy into it only what was uploaded,
  in the aux command buffer that already does the index/uniform copies, and
  bind the mirror. This is the brief's "stage vertex data into device-local
  memory once per frame".
- **U (per-draw constant reload).** Every draw re-uploads the whole VS+PS
  uniform layout (the 192-entry constant file is in it) to a new UBO offset.
  Turnip then rebinds descriptors, invalidates the bindless caches, and the
  preamble reloads the pushed constants from memory. The fix is a change to
  how uniforms are laid out and bound (`vk/shaders.c`, the GLSL generators),
  **outside this lane's territory**.

The counters cannot separate V from U: both scale with draws (`SBnd` = `BE`,
one vertex bind per draw). V is the one the brief's territory can fix, and
the one the brief's step 2 asked about. The A/B is also its falsifier: if V
is the cost, heavy-view GPU ms per draw falls; if the slope does not move, V
is refuted and U is next (section 7).

What the reading establishes: the allocation flags ask for cached memory, and
the only cached type this driver can offer on ARM is IO-coherent. What it does
not establish: that the Nova's kernel exposes that type (the B arm's
`[vtxmirror]` line answers it), and how much of the 12-14 us the snoop costs.
Only the arm can say that.

Probability, stated because the brief asks for ranking by probability x win:
V ~35-40% to be most of the slope (it is the one memory-latency path on every
draw that is pathological on this SoC); U similar, but unfixable in this
territory; the rest (driver per-draw state cost, shader work) ~25%. Win if V
holds: heavy views 35-40 ms -> under 30, and every title whose draws read
guest vertex buffers gains. The arm decides V either way, and a FAIL hands U
a clean field.

## 4. The fix (step 3): a device-local vertex-RAM mirror (57fe561924, vk/draw.c only)

- `init_vertex_ram_mirror` (from `pgraph_vk_init_pipelines`) creates one
  device-local buffer the size of vertex RAM (64 MB; `AUTO_PREFER_DEVICE`, no
  host access) and logs both memory types. `HAKUX_VTX_MIRROR=0` leaves it off.
- `sync_vertex_ram_buffer` records each range it uploads (`vtx_mirror_note`,
  merged, 64 slots, then the bounding range).
- At finish, in the aux command buffer, `flush_vertex_ram` copies those ranges
  from the current host copy into the mirror. If the frame's flush range is not
  explained by the recorded ranges, or covers all of vertex RAM, another writer
  did a full refresh (the initial upload in renderer.c, the render thread's
  flush op), and the whole flush range is copied. The aux CB's existing
  barriers order the copy: WAR against every earlier submission at its top,
  TRANSFER_WRITE -> VERTEX_ATTRIBUTE_READ before the main CB.
- `bind_vertex_buffer` and the reorder path's `snapshot_vertex_buffers` bind
  the mirror for vertex-RAM attributes.
- The frame-switch catch-up (#39) still memcpys the incoming host copy up to
  date, but is flushed on the spot instead of being added to the flush range.
  The mirror already holds those bytes, and the span can cover most of vertex
  RAM.
- Same bytes, same moment: a frame's host copy is not written again until that
  frame is current again, after its fence. So the draws of a command buffer read
  what the host copy held at its finish, before and after. Pixels should not
  move (registered).
- `[vtxmirror] flips= fin= copies= full= ovf= kb=` every 120 flips: what the
  copies cost.
- Outside the territory, and the natural home if this stays: the mirror's state
  belongs in `PGRAPHVkState` (`vk/renderer.h`) and its allocation in
  `vk/buffer.c`, where the host copies are made. Here it is file-static in
  draw.c, because the brief's territory is draw.c/renderer.c/surface.c.
- Local checks: `.scratch/cc_check.py`, the NDK clang line from the main
  tree's `compile_commands.json` pointed at this worktree's draw.c, release and
  `NV2A_PERF_LOG=1`: rc 0, and every warning it prints is pre-existing (none in
  the new code).

## 5. Prediction and runs (step 4-5)

Registered before any run (commit after 57fe561924):
- `bf2stall433-bf2-soak.json`: BF2, Nova, default regimen, perflog, 420 s,
  frames every 20 s, 3 runs per arm, A = master b71f92a12a, B = 57fe561924.
  Judged by `armread.py` (this dir), which reproduces collapse433's table from
  its soaks (GMEM vs sysmem gives slopes 0.0119 / 0.0121 and P1 0.946, which is
  the view-to-view noise level).
- `bf2stall433-pixels.json` (98 suites, one run per arm) and
  `bf2stall433-band.json` (Stencil, Vertex_shader_rounding_tests; three runs
  per arm): every capture byte-identical. Registered with `register_pixels.py`.
  These have golden keys, so the arms job queues them, not this lane.
- `bf2stall433-gta-soak.json`: the second draw-heavy title, no regression.
  NOT queued: the brief caps this lane at 6 Nova runs and the BF2 pair takes
  all 6. Needs six more runs from lane.local.
- No hold is taken for the soaks: a hold stops the Nova's dispatcher claiming,
  so it blocks the lane's own request (collapse433's process note).

## 6. The pilot pair refutes V (2026-10-02 06:52-07:11 PDT)

A1 `1-1790948452-lane.bf2stall433-3362375` (master b71f92a12a, apk
4e340d5f2591) and B1 `1-1790948456-lane.bf2stall433-3362482` (57fe561924, apk
c5f203ffb38a). Both reached `mark gameplay` (A1 07:02:39, B1 07:09:53). The
route ends ~38-61 s later: 420 s leaves that little after BF2's menus. Neither
run crashed. `armread.py`:

| | A1 master | B1 mirror |
|---|---|---|
| rows (60-flip windows, -45 s..end) | 29 | 39 |
| heavy rows (BE >= 1800) | 17 | 20 |
| heavy-view GPU ms, median | 35.9 | **36.0** |
| heavy-view fps | 16.2 | 17.4 |
| fit GPU ms per draw | 0.0111 | 0.0099 |
| light views (BE < 1200) GPU ms | 16.5 | 21.4 |
| transfer GPU ms (X) | 2.0 | 2.4 |

- **P0 PASS, the premise holds:** `[vtxmirror] on: 64 MB; host type 1 flags
  0xf cached=1 coherent=1; mirror type 0 flags 0x7 host_visible=1`. The host
  copies ARE IO-coherent cached memory, and the mirror is the write-combine
  type (no snoop).
- **P1 FAIL: heavy-view GPU ms B/A = 1.004** against a predicted <= 0.80.
  Both arms clear the registered resolution floor (>= 8 heavy rows each). The
  snoop path is real and was removed, and the per-draw GPU cost did not move.
  **V is refuted as the cause.**
- Copy cost, measured: in gameplay BF2 re-uploads ~63-67 MB of vertex data per
  120 flips (~0.5 MB a flip; dynamic vertex buffers), against ~0.5 MB per 120
  flips in the menus. The light-view GPU rise (16.5 -> 21.4) is within the
  view-to-view spread (collapse433's GMEM/sysmem pair differed by 5.5 ms there),
  so it is not attributed.
- So the rest of the 3+3 was not queued: it would firm up a null on a change
  that should not ship. The fix is reverted on this branch (draw.c restored
  from master). Its pixel and band predictions are deleted from the branch so
  the arms job does not queue them again, and their 4 queued arms
  (`1790949781-arms-bf2stall433-{base,fix}-*`, `1790949783-...`) were moved to
  `queue/withdrawn/`. The GTA prediction for the same change is deleted too.
  The code stays in history at 57fe561924.
- Do not repeat: a device-local copy of vertex RAM, or any other change to
  where vertex data is fetched from, for the per-draw GPU cost. The IO-coherent
  fetch costs nothing measurable on the Nova.

## 7. Next: is the per-draw cost a stall or throughput? (syncdraw)

`bf2stall433-syncdraw.json`, registered before the run: one master run with
`TU_DEBUG=sysmem,syncdraw`, against collapse433's sysmem soak (renderer
byte-identical: `git diff 8b45e7c15c b71f92a12a -- hw/
android/app/src/main/cpp/` is empty). Syncdraw drains the GPU before every
draw. If the heavy-view GPU ms barely rises (S), draws are already serialized
by something in our stream. The prime suspect is then the per-draw UBO rebind
(new dynamic offset -> new Turnip descriptor set, bindless invalidation,
constant reload). If it rises by >= 60% (T), draws normally overlap, and the
cost is per-draw work.
