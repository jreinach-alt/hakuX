# lane.drawrec1010 -- per-draw recording at the NFS Most Wanted race start (#433, 0.5)

Step 3 of `docs/lanes/nfs30plan1010/PLAN.md` (on lane/nfs30plan1010): cut the PFIFO
thread's per-draw recording cost by about a third. The census decides what gets built.

## 1. What is on master before this lane (read from the code)

`begin_pre_draw_inner()` takes one of three paths per draw:

- **SFP**, the super-fast path: nothing changed that it checks; no uniform update, no
  descriptor work.
- **MFP**: `update_shader_uniforms()` + `update_descriptor_sets()` only.
- **Full**: `create_pipeline()` (early hit if no generation moved; else bind textures if
  their generations moved, `bind_shaders()` if the shader generation moved, else
  `update_shader_uniforms()`; then `check_pipeline_dirty()`, `init_pipeline_key()` +
  memcmp against the bound pipeline, `fast_hash()` + LRU lookup), then setup and
  `update_descriptor_sets()`.

### 1.1 `shader_bindings_changed` is sticky (a candidate cost, to be measured)

- Set only in `pgraph_vk_bind_shaders()` when the state really differs
  (`hw/xbox/nv2a/pgraph/vk/shaders.c:2202`).
- Cleared only at the entry of `pgraph_vk_bind_shaders()` (`shaders.c:2149`), and
  saved/cleared/restored around the draw-queue replay (`draw.c` ~7516-7770).
- `bind_shaders()` runs only when `shader_state_gen` moved, the primitive mode changed,
  or `program_data_dirty`. So after a shader change, every following draw until the next
  shader-generation bump enters with the flag still true, and each of them:
  - misses SFP (`draw.c:5515`, `sfp_miss_shader_changed`) and MFP (`draw.c:5727`);
  - misses the `create_pipeline()` early hit (`draw.c:2463`);
  - has `check_pipeline_dirty()` true (`draw.c:2184`), so builds the key and memcmps it
    (a same-key hit);
  - has `need_new_ubo_set` true in `update_descriptor_sets()` (`shaders.c:906`, `:972`),
    so writes a fresh UBO descriptor set (`vkUpdateDescriptorSets`) every draw. The UBO
    binding is `UNIFORM_BUFFER_DYNAMIC` with range = the layout's total size, so a set
    written for a binding stays valid while the binding is the same; only the dynamic
    offsets move.
- The census measures this directly: `shc_in` (draws entering with the flag set),
  `shc_stale` (of those, the shader binding did not change), `shc_stale_full` (and the
  draw took the full path), and `ubo_sets_samesb` (a UBO set written though the binding
  did not change).

### 1.2 First cut from data already on disk (no new device time)

Run `1-1791649387-nfs30plan1010-2138210` (lane.nfs30plan1010, perflog, master at
ab1acc4154 in hw/, race start, route `nfs-mw-quickrace`). Per-60-frame `xemu-sfp`
counters, two windows at the race start:

| window | draws | SFP hits | first miss = shader changed | = uniforms | = non-dynamic regs |
|---|---|---|---|---|---|
| 1 | 85,037 | 355 (0.4%) | 41,536 (49%) | 26,088 (31%) | 10,245 (12%) |
| 2 | 118,814 | 504 (0.4%) | 50,047 (42%) | 39,554 (33%) | 21,991 (19%) |

Same run, `xemu-work` per frame: BE 947 draws, PBnd 196 (pipeline rebound on ~21%
of draws), SBnd 940. Phase (ms/frame): Draw 12.3 [Syn 2.5, Pipe 4.6 (Tx 1.3, Sh 2.8,
Lu 0.4), Desc 1.8, Setup 1.0, Mfp 1.0], Fin 12.6. `ubosz`: the vertex constants
c96-c107 were uploaded 52-72k times per 60 frames.

Reading: half the SFP misses are "shader changed" while only ~21% of draws rebind the
pipeline, which is what a sticky flag would produce. The census separates that from
real shader changes.

## 2. The census instrument (`HAKUX_DRAWCENSUS=1`, default off)

All in `hw/xbox/nv2a/pgraph/vk/draw.c`; no other file. Off, the cost is a byte store
per path taken in `begin_pre_draw_inner()`/`create_pipeline()` (which path, which
outcome) and one predictable branch per draw. On, a wrapper around `begin_pre_draw()`
snapshots state before and diffs it after, against the previous drawn draw:

- the shader and pipeline binding, vertex attribute/binding descriptions, the four
  bound textures (and direct surface views), the colour/zeta surface, the primitive;
- every PGRAPH register word, grouped: combiners/shader program/clip mode (rc), texture
  (rt), CSV0/CSV1 + point size (rl), blend/depth/raster static bits (rb), the bits in
  `pgraph_reg_dynamic_mask_table` (rd), uniform-fed (factors, fog, bump, eye: rf),
  window clip (rw), anything else (ro, with its top addresses);
- c[] by row; lighting/material by hash; the uploaded uniform bytes by hash of both
  layouts (the bytes `uniform_copy` produced).

Class per draw (first that applies): surf, shader, pipe, tex, reg, uni, dyn, same.
Decision per the brief: same+dyn+uni >= 50% -> reuse; else same >= 40% -> batching;
else stop.

Printed once per 60 frames under `hakuX-stall` (`census`, `census-bits`, `census-path`,
`census-cost`, `census-crow`, `census-mask`, `census-ro`); read with
`docs/lanes/drawrec1010/censusread.py <result dir>` (default window: mark-2 .. mark+13
for each `mark gameplay|goN`).

Cost when on: a diff of the 2,048-word register file (strided in `regs_`) and 192 c[]
rows per draw, ~2-3 us/draw estimated; it is a classification run, not a timing run.
Type-checked with host gcc and the dispatcher's NDK clang (NV2A_PERF_LOG 0 and 1).

## 3. simpleperf of the PFIFO thread

The brief asks for one `simpleperf record` of the PFIFO thread on the plain build over
two race starts. No lane-reachable path runs it: request.sh has no profiler option,
route.sh has no hook, and profile_guest.sh drives the device directly (lanes may not).
Asked on the board (`board-requests/drawrec1010.md`). Not a blocker for the census
decision.

## 4. Runs

| id | what | build | result |
|---|---|---|---|
| (queued below) | census, race start, perdrawon1010's switches on | perflog | |

## 5. Do not repeat

- Do not `cd` out of the worktree in a Bash call: the session's working directory follows.
