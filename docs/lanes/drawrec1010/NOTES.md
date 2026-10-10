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
Asked on the board (`board-requests/drawrec1010.md`); no answer by the end of attempt 2.
It was not needed for the decision: the perflog phase split plus the `[rdc]` TLB-walk
counters below name the largest per-draw cost directly (section 5.3).

## 4. Runs

| id | what | build | result |
|---|---|---|---|
| 1-1791656193-drawrec1010-4097387 | census, race start, 12 starts, HAKUX_UNI_BULK/UBERCACHE/FOGCACHE=1 | perflog @ e7f2e720c8 | DONE; 12 marks, 68 windows, section 5 |

## 5. Census result (run 1-1791656193-drawrec1010-4097387)

Reader output, whole: `census-1-1791656193.md` in this directory
(`censusread.py`, default window mark-2..mark+13 for each of the 12 marks). The player
is moving: `s1-g11.png` shows 64 mph, `s8-g11.png` 76 mph.

68 windows (4,080 frames), 4,749,007 draws, 1,164 draws/frame.

### 5.1 Class of each draw against the previous one (first that applies)

| class | % of draws | cum % |
|---|---|---|
| same (nothing changed) | 24.4 | 24.4 |
| dyn (dynamic state only) | 0.0 | 24.4 |
| uni (uniforms only) | 38.6 | 63.0 |
| reg (a key-feeding register) | 9.5 | 72.6 |
| tex | 15.6 | 88.2 |
| pipe | 0.2 | 88.4 |
| shader | 9.9 | 98.3 |
| surf | 1.7 | 100.0 |

**Decision: same+dyn+uni = 63.0% >= 50% -> step 2, reuse.** (same alone 24.4%, under
the 40% batching bar.)

Inputs changed, % of draws: shader binding 11.4, pipeline binding 11.6, vertex layout
8.3, texture 27.4, surface 1.7, primitive 1.2, c[] 57.8, uploaded uniform bytes 67.8;
registers: combiners 5.8, texture 27.4, CSV/point 9.5, blend/depth 3.0, dynamic-only
6.4, uniform-fed 0.3, window clip 0.7, other 21.8 (0x0FC4 CHEOPS_OFFSET 20.2,
0x0B10 3.1). c[] rows changed per draw: none 42.2%, 9-16 rows 46.6% (block c96-111 on
51% of draws: a per-draw transform). Commonest masks: c[]+uniform bytes 35.5%, nothing
24.4%, c[]+bytes+other reg 7.8%, texture 5.6%.

### 5.2 What the recorder does with them

| | % of draws |
|---|---|
| path SFP / MFP / full | 0.5 / 31.4 / 68.1 |
| create_pipeline: not entered / not dirty / same key / LRU / miss | 31.9 / 8.2 / 48.3 / 11.6 / 0.0 |
| bind_shaders called | 42.0 |
| entered with `shader_bindings_changed` set | 37.2 |
| ... binding had not changed (stale flag), all on the full path | 31.0 |
| UBO descriptor set written / ... binding unchanged | 37.2 / 25.8 |
| uniform bytes uploaded / ... same bytes, same binding | 72.0 / 4.1 |
| a same/dyn/uni draw on the full path | 36.1 |
| a "same" draw that missed SFP | 23.9 |

SFP first miss (same run, `xemu-sfp`): shader changed 36.6%, uniforms 32.9%,
non-dynamic register generation 24.1%, primitive 4.3%, no render pass 1.7%.

Reading: the stale `shader_bindings_changed` flag (section 1.1) is real and large:
31% of all draws take the full path and write a fresh UBO set only because of it. The
uniform change is inherent (a per-draw transform in c96-c111 on half the draws), so
"upload only dirty ranges" saves little at this scene; the reuse that is available is
in the path choice, not in the upload.

### 5.3 The largest per-draw cost is the vertex sync's TLB walk, not the key

Clean baseline, no census: lane.perdrawon1010's runs `1-1791645060-perdrawon1010-726861`
and `1-1791645063-perdrawon1010-728778` (perflog, F1-F3 on, `nfs-mw-quickrace`),
read with phaseread.py by that lane:

| window | Draw ms/frame | draws/frame | us/draw | Syn | Pipe (Sh) | Desc | Setup | Mfp | pace ms |
|---|---|---|---|---|---|---|---|---|---|
| countdown | 12.2 | 1,578 | 7.7 | 4.0 | 3.7 (1.7) | 0.5 | 1.0 | 1.0 | 44.2 |
| GO..+11.5 s | 9.4 | 1,085 | 8.7 | 2.9 | 3.2 | | | | |

F1-F3 already took Desc from 2.7 to 0.5 and Mfp from 3.9 to 1.0, so the brief's
Pipe/Desc/Mfp targets (written from the pre-F1-F3 runs 1-1791649387/88) are stale.
`Syn` (the vertex sync) is now the largest phase, and the `[rdc]` counters say what it
is. `vtx=` is the TLB walk that `sync_vertex_ram_buffer()` runs through
`physical_memory_dirty_bits_cleared()` each time a vertex range is found dirty
(calls/us/pages/entries reset), per 60 flips, first windows after `mark go2`:

| run | walks/60 flips | us | walks/flip | ms/flip | us/walk | entries reset/walk |
|---|---|---|---|---|---|---|
| 726861 (no census) | 14,379 | 232,528 | 240 | 3.88 | 16.2 | 1.0 |
| 726861 | 12,325 | 202,318 | 205 | 3.37 | 16.4 | 1.0 |
| 726861 | 9,453 | 160,257 | 158 | 2.67 | 17.0 | 1.0 |
| 726861 (warm) | 4,740 | 77,328 | 79 | 1.29 | 16.3 | 1.0 |
| 4097387 (census) | 14,543 | 225,634 | 242 | 3.76 | 15.5 | 1.0 |
| 4097387 | 12,061 | 189,214 | 201 | 3.15 | 15.7 | 1.0 |

Each walk scans every live TLB entry (~8,272; `HAKUX_TCG68_RD` already limits it to the
live modes) to re-arm about one entry. At the cold start that is 3.4-3.9 ms per flip of
the 4.0 ms `Syn`, a third of the 12.2 ms recording. lane.dirtytlb (#575) priced the
span and live-mode variants of the walk and left "one walk per flip with a pending
bitmap" unpriced; that is what step 2 adds.

## 6. Step 2 plan, ranked by expected impact (probability x win at the race start)

| part | what | win if it works | P | evidence for P |
|---|---|---|---|---|
| V | vertex sync: clear the bits and copy, but owe the TLB re-arm to a pending bitmap walked once per flip (or after a re-upload budget); a page owed a walk is re-copied on every touch until walked, and once more after | ~2.5-3.5 ms/frame cold, ~1 ms warm | 0.6 | the walk is 3.4-3.9 of 4.0 ms Syn (5.3); the unknown is how often a page is re-touched before the flip, which the new counters measure |
| R1 | clear the stale `shader_bindings_changed` once the full path has consumed it | ~0.5-1 ms/frame | 0.6 | 31% of draws on the full path for it alone (5.2); what they save is the key build + memcmp, setup and a UBO set write each |
| R3 | texture-only changes skip the shader-state rebuild | ~0.3-0.5 ms/frame | 0.3 | 27% of draws change texture, 11% change binding; needs the glsl state code, outside territory |
| R4 | CHEOPS_OFFSET off the generations | ~0 | | its draws also change uniforms, so they miss SFP anyway (5.1) |

V and R1 go behind `HAKUX_DRAWREC=1` with per-part disables
(`HAKUX_DRAWREC_VTX=0`, `HAKUX_DRAWREC_SHC=0`). Push constants for the dynamic offsets:
not built, the dynamic-only class is 0.0%.

## 7. Why attempt 1 did not finish

Attempt 1 built the census instrument and reader, queued the census arm
(1-1791656193) and ended correctly on `WAITING` with that run id: a headless session
cannot wait 90 minutes for a device run. The run is DONE; attempt 2 starts from its
result.

## 8. Do not repeat

- Do not `cd` out of the worktree in a Bash call: the session's working directory follows.
- `phaseread.py` takes `--window=-2,13` (with the equals sign); `-2,13` as a separate
  argument is read as an option.
- The vertex-sync counters `Vsyn` are on the overlay only, not in logcat; the `[rdc]`
  line is the logcat source for the walk cost.
