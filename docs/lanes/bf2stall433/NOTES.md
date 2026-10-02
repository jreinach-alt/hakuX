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
  !DETECT_ARCH_ARM`), so the only HOST_CACHED type is the cached-coherent one,
  allocated with `KGSL_MEMFLAGS_IOCOHERENT | KGSL_CACHEMODE_WRITEBACK`. The
  allocation succeeded on the Nova (buffer_init logs all three), so a
  HOST_CACHED type exists, and it is that one.
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

Not a guess at the mechanism: the IO-coherent placement is read off the
allocation flags and the driver source. What is not known is how much of the
12-14 us it costs. Only the arm can say that.

## 4. The fix (step 3)
(in progress)
